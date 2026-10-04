from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.schemas.payment import (
    PaymentConfirmRequest,
    PaymentCreate,
    PaymentResponse,
    RefundRequest,
)
from app.services.payment_service import payment_service

router = APIRouter(prefix="/payments", tags=["payments"])

@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def initiate_payment(
    data: PaymentCreate,
    user_id: Optional[int] = Depends(get_current_user_id),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
):
    resolved_user_id = data.user_id or user_id or 1
    return await payment_service.create_payment(
        db, data, resolved_user_id, idempotency_key=idempotency_key
    )

@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment_status(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await payment_service.get_payment(db, payment_id)

@router.post("/{payment_id}/pay", response_model=PaymentResponse)
async def confirm_payment_checkout(
    payment_id: int,
    body: Optional[PaymentConfirmRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    method = body.payment_method_id if body else "pm_card_visa"
    return await payment_service.confirm_payment(db, payment_id, method)

@router.post("/{payment_id}/refund", response_model=PaymentResponse)
async def refund_payment(
    payment_id: int,
    body: Optional[RefundRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    reason = body.reason if body else "user_cancellation"
    return await payment_service.refund_payment(db, payment_id, reason)

@router.post("/webhook")
async def payment_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db),
):
    raw_body = await request.body()
    result = await payment_service.handle_webhook(db, raw_body, stripe_signature or "")
    return result

@router.get("/{payment_id}/checkout", response_class=HTMLResponse)
async def render_checkout_page(payment_id: int, db: AsyncSession = Depends(get_db)):
    payment = await payment_service.get_payment(db, payment_id)
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
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
                <span class="badge {'badge-succeeded' if payment.status == 'SUCCEEDED' else 'badge-pending'}">{payment.status}</span>
            </div>
            <div class="detail"><span>Номер брони:</span><strong>#{payment.booking_id}</strong></div>
            <div class="detail"><span>ID гостя:</span><strong>#{payment.user_id}</strong></div>
            <div class="detail"><span>Провайдер:</span><strong>{payment.provider}</strong></div>
            <div class="amount">{payment.amount} {payment.currency}</div>
            
            <div id="action-area">
                {'''
                <button class="btn" onclick="submitPayment()">Оплатить тестовой картой Visa</button>
                ''' if payment.status == 'PENDING' else f'''
                <p style="color: #10b981; text-align: center; font-weight: 600;">✓ Оплата успешно завершена!</p>
                <p style="text-align: center;"><a href="{payment.receipt_url or '#'}" style="color: #38bdf8;" target="_blank">Посмотреть электронный чек</a></p>
                '''}
            </div>
        </div>
        <script>
            async function submitPayment() {{
                const btn = document.querySelector('.btn');
                if (btn) {{
                    btn.disabled = true;
                    btn.innerText = 'Обработка платежа в шлюзе...';
                }}
                try {{
                    const res = await fetch('/api/v1/payments/{payment.id}/pay', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
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
    return HTMLResponse(content=html_content)
