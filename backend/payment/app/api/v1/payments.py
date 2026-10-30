import html
import json
import urllib.parse
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user, get_optional_user, require_admin
from app.models.payment import Payment, PaymentStatus
from app.schemas.payment import (
    PaymentConfirmRequest,
    PaymentCreate,
    PaymentResponse,
    RefundRequest,
)
from app.services.payment_service import payment_service
from app.services.stripe_gateway import WebhookVerificationError

router = APIRouter(prefix="/payments", tags=["payments"])


def to_response(payment: Payment, user: Optional[CurrentUser]) -> PaymentResponse:
    response = PaymentResponse.model_validate(payment)
    # Секрет страницы оплаты отдаём только владельцу, пока платёж не завершён
    is_owner = user is not None and user.id == payment.user_id
    if is_owner and payment.status == PaymentStatus.PENDING.value:
        response.client_secret = payment.client_secret
        response.checkout_url = f"/api/v1/payments/{payment.id}/checkout?secret={payment.client_secret}"
    else:
        response.client_secret = None
    return response


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def initiate_payment(
    data: PaymentCreate,
    user: CurrentUser = Depends(get_current_user),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key", max_length=255),
    db: AsyncSession = Depends(get_db),
):
    payment = await payment_service.create_payment(
        db, data.booking_id, user, idempotency_key=idempotency_key
    )
    return to_response(payment, user)


@router.get("/my", response_model=list[PaymentResponse])
async def list_my_payments(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    payments = await payment_service.list_user_payments(db, user)
    return [to_response(payment, user) for payment in payments]


@router.post("/webhook")
async def payment_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db),
):
    raw_body = await request.body()
    try:
        return await payment_service.handle_webhook(db, raw_body, stripe_signature or "")
    except WebhookVerificationError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature")


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment_status(
    payment_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    payment = await payment_service.get_payment_for_user(db, payment_id, user)
    return to_response(payment, user)


@router.post("/{payment_id}/pay", response_model=PaymentResponse)
async def confirm_payment_checkout(
    payment_id: int,
    body: Optional[PaymentConfirmRequest] = None,
    user: Optional[CurrentUser] = Depends(get_optional_user),
    client_secret: Optional[str] = Header(None, alias="X-Client-Secret"),
    db: AsyncSession = Depends(get_db),
):
    # Оплатить может владелец (по токену) или страница оплаты (по секрету платежа)
    if client_secret:
        await payment_service.get_payment_by_secret(db, payment_id, client_secret)
    elif user is not None:
        payment = await payment_service.get_payment_for_user(db, payment_id, user)
        if payment.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the payer can confirm the payment")
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    await db.rollback()
    method = body.payment_method_id if body else "pm_card_visa"
    payment = await payment_service.confirm_payment(db, payment_id, method)
    return to_response(payment, user)


@router.post("/{payment_id}/refund", response_model=PaymentResponse)
async def refund_payment(
    payment_id: int,
    body: Optional[RefundRequest] = None,
    admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    reason = (body.reason if body else None) or "admin_refund"
    payment = await payment_service.refund_payment(db, payment_id, reason)
    return to_response(payment, admin)


def _js_string(value: str) -> str:
    # JSON-строка, безопасная внутри <script>
    return json.dumps(value).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


@router.get("/{payment_id}/checkout", response_class=HTMLResponse)
async def render_checkout_page(
    payment_id: int,
    secret: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
):
    payment = await payment_service.get_payment_by_secret(db, payment_id, secret)
    e = html.escape
    is_pending = payment.status == PaymentStatus.PENDING.value
    badge = "badge-succeeded" if payment.status == PaymentStatus.SUCCEEDED.value else "badge-pending"

    if is_pending:
        wa_text = f"Здравствуйте! Чек оплаты брони №{payment.booking_id} на сумму {payment.amount} сом"
        wa_link = f"https://wa.me/996555000001?text={urllib.parse.quote(wa_text)}"
        action_html = f"""
        <div style="text-align: center; margin: 16px 0;">
            <p style="color: #94a3b8; font-size: 14px; margin-bottom: 12px;">
                Отсканируйте QR-код в приложении банка (Mbank / Optima / О!Деньги) для оплаты депозита:
            </p>
            <div style="background: white; padding: 12px; border-radius: 12px; display: inline-block; margin-bottom: 10px;">
                <svg width="180" height="180" viewBox="0 0 24 24" fill="none">
                    <rect x="2" y="2" width="8" height="8" rx="1" fill="#0f172a"/>
                    <rect x="4" y="4" width="4" height="4" fill="white"/>
                    <rect x="14" y="2" width="8" height="8" rx="1" fill="#0f172a"/>
                    <rect x="16" y="4" width="4" height="4" fill="white"/>
                    <rect x="2" y="14" width="8" height="8" rx="1" fill="#0f172a"/>
                    <rect x="4" y="16" width="4" height="4" fill="white"/>
                    <rect x="14" y="14" width="3" height="3" fill="#0f172a"/>
                    <rect x="19" y="14" width="3" height="3" fill="#0f172a"/>
                    <rect x="14" y="19" width="3" height="3" fill="#0f172a"/>
                    <rect x="19" y="19" width="3" height="3" fill="#0f172a"/>
                    <rect x="11" y="5" width="2" height="14" fill="#0f172a"/>
                    <rect x="5" y="11" width="14" height="2" fill="#0f172a"/>
                </svg>
            </div>
            <p style="font-size: 13px; color: #94a3b8; margin: 4px 0 16px;">Получатель: Бар «Пивница»</p>
        </div>
        <button class="btn" onclick="submitPayment()">Я оплатил(а) депозит</button>
        <p style="text-align: center; margin-top: 14px;">
            <a href="{wa_link}" target="_blank" rel="noopener noreferrer"
               style="color: #22c55e; text-decoration: none; font-size: 14px; font-weight: 600;">
                💬 Отправить чек в WhatsApp
            </a>
        </p>
        """
    elif payment.status == PaymentStatus.SUCCEEDED.value:
        action_html = (
            '<p style="color: #10b981; text-align: center; font-weight: 600;">✓ Оплата успешно завершена!</p>'
            f'<p style="text-align: center;"><a href="{e(payment.receipt_url or "#")}" style="color: #38bdf8;" '
            'target="_blank" rel="noopener noreferrer">Посмотреть электронный чек</a></p>'
        )
    else:
        action_html = f'<p style="text-align: center; color: #f87171;">Статус платежа: {e(payment.status)}</p>'

    html_content = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta name="referrer" content="no-referrer">
        <title>Оплата бронирования | Pivnitsa Pub</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #0f172a;
                color: #f8fafc;
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                margin: 0;
            }}
            .card {{
                background: #1e293b;
                border: 1px solid #334155;
                border-radius: 16px;
                padding: 32px;
                width: 100%;
                max-width: 440px;
                box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
            }}
            h2 {{ margin-top: 0; color: #38bdf8; font-size: 24px; }}
            .detail {{ display: flex; justify-content: space-between; margin: 12px 0; color: #94a3b8; }}
            .detail strong {{ color: #f8fafc; }}
            .amount {{ font-size: 28px; font-weight: 700; color: #10b981; margin: 20px 0; text-align: center; }}
            .btn {{
                background: #38bdf8;
                color: #0f172a;
                font-weight: 700;
                font-size: 16px;
                border: none;
                border-radius: 8px;
                padding: 14px;
                width: 100%;
                cursor: pointer;
                transition: background 0.2s;
            }}
            .btn:hover {{ background: #0284c7; }}
            .badge {{
                display: inline-block;
                padding: 4px 10px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
            }}
            .badge-pending {{ background: #ca8a04; color: #fef08a; }}
            .badge-succeeded {{ background: #16a34a; color: #dcfce7; }}
            .status-box {{ text-align: center; margin-bottom: 16px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Pivnitsa Pub</h2>
            <p style="color: #94a3b8;">Безопасная оплата бронирования столика (PCI-DSS)</p>
            <hr style="border: 0; border-top: 1px solid #334155; margin: 16px 0;">
            <div class="status-box">
                <span class="badge {badge}">{e(payment.status)}</span>
            </div>
            <div class="detail"><span>Номер брони:</span><strong>#{payment.booking_id}</strong></div>
            <div class="detail"><span>Провайдер:</span><strong>{e(payment.provider)}</strong></div>
            <div class="amount">{e(str(payment.amount))} {e(payment.currency)}</div>
            <div id="action-area">{action_html}</div>
        </div>
        <script>
            const PAYMENT_ID = {payment.id};
            const CLIENT_SECRET = {_js_string(secret)};
            async function submitPayment() {{
                const btn = document.querySelector('.btn');
                if (btn) {{
                    btn.disabled = true;
                    btn.innerText = 'Обработка платежа в шлюзе...';
                }}
                try {{
                    const res = await fetch(`/api/v1/payments/${{PAYMENT_ID}}/pay`, {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json', 'X-Client-Secret': CLIENT_SECRET }},
                        body: JSON.stringify({{ payment_method_id: 'pm_card_visa' }})
                    }});
                    if (res.ok) {{
                        location.reload();
                    }} else {{
                        alert('Ошибка при оплате');
                        if (btn) btn.disabled = false;
                    }}
                }} catch (e) {{
                    alert('Ошибка сети: ' + e);
                    if (btn) btn.disabled = false;
                }}
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, headers={"Cache-Control": "no-store"})
