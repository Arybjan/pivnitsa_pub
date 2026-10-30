import json
import logging
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.security import CurrentUser
from app.models.payment import OutboxEvent, Payment, PaymentStatus
from app.services.booking_client import BookingServiceClient, booking_client, parse_datetime
from app.services.stripe_gateway import StripePaymentGateway, gateway

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = (
    PaymentStatus.PENDING.value,
    PaymentStatus.SUCCEEDED.value,
    PaymentStatus.REFUND_PENDING.value,
)


def add_outbox_event(db: AsyncSession, routing_key: str, payload: Dict[str, Any]) -> None:
    # Без commit: событие сохраняется атомарно вместе со сменой статуса платежа
    db.add(OutboxEvent(routing_key=routing_key, payload=json.dumps(payload)))


def payment_event_payload(payment: Payment, **extra: Any) -> Dict[str, Any]:
    return {
        "payment_id": payment.id,
        "booking_id": payment.booking_id,
        "user_id": payment.user_id,
        "amount": str(payment.amount),
        "currency": payment.currency,
        **extra,
    }


class PaymentService:
    def __init__(
        self,
        bookings: BookingServiceClient = booking_client,
        payment_gateway: StripePaymentGateway = gateway,
    ):
        self.bookings = bookings
        self.gateway = payment_gateway

    async def create_payment(
        self,
        db: AsyncSession,
        booking_id: int,
        user: CurrentUser,
        idempotency_key: Optional[str] = None,
    ) -> Payment:
        # 1. Повтор запроса с тем же Idempotency-Key возвращает тот же платёж
        if idempotency_key:
            existing = await self._get_by_idempotency_key(db, idempotency_key)
            if existing:
                return self._check_idempotent_owner(existing, user)

        # 2. Бронь проверяет Booking Service: существует, принадлежит пользователю
        booking = await self.bookings.get_booking(booking_id, user.token)

        if int(booking["user_id"]) != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Booking belongs to another user")

        if booking["status"] != "PENDING_PAYMENT":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Booking is not awaiting payment (status: {booking['status']})",
            )

        if parse_datetime(booking["expires_at"]) <= datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Booking hold has expired")

        # 3. Уже есть активный платёж по этой брони
        active = await self._get_active_for_booking(db, booking_id)
        if active:
            return self._resolve_active_payment(active, user)

        # 4. Сумма депозита: цена стола (если задана) или тариф за гостя
        amount = None
        if booking.get("total_amount"):
            amount = Decimal(str(booking["total_amount"])).quantize(Decimal("0.01"))
        elif booking.get("prepayment"):
            amount = Decimal(str(booking["prepayment"])).quantize(Decimal("0.01"))

        if not amount or amount <= Decimal("0.00"):
            amount = (settings.DEPOSIT_PER_GUEST * int(booking["guests"])).quantize(Decimal("0.01"))

        payment = Payment(
            booking_id=booking_id,
            user_id=user.id,
            amount=amount,
            currency=settings.CURRENCY,
            status=PaymentStatus.PENDING.value,
            provider="STRIPE",
            idempotency_key=idempotency_key,
            client_secret=secrets.token_urlsafe(32),
        )

        try:
            db.add(payment)
            await db.flush()
        except IntegrityError:
            # Параллельный запрос успел первым (уникальный индекс по брони или ключу)
            await db.rollback()
            if idempotency_key:
                existing = await self._get_by_idempotency_key(db, idempotency_key)
                if existing:
                    return self._check_idempotent_owner(existing, user)
            active = await self._get_active_for_booking(db, booking_id)
            if active:
                return self._resolve_active_payment(active, user)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict occurred while processing payment",
            )

        intent = await self.gateway.create_intent(
            payment_id=payment.id,
            amount=payment.amount,
            currency=payment.currency,
            description=f"Pivnitsa Pub: Reservation #{payment.booking_id}",
            metadata={"booking_id": str(payment.booking_id), "user_id": str(payment.user_id)},
        )

        payment.provider_payment_id = intent["id"]
        payment.receipt_url = intent.get("receipt_url")
        await db.commit()
        await db.refresh(payment)
        return payment

    async def get_payment(self, db: AsyncSession, payment_id: int, for_update: bool = False) -> Payment:
        stmt = select(Payment).where(Payment.id == payment_id).execution_options(populate_existing=True)
        if for_update:
            stmt = stmt.with_for_update()
        payment = (await db.execute(stmt)).scalars().first()
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment #{payment_id} not found",
            )
        return payment

    async def get_payment_for_user(self, db: AsyncSession, payment_id: int, user: CurrentUser) -> Payment:
        payment = await self.get_payment(db, payment_id)
        if payment.user_id != user.id and not user.is_admin:
            # 404, а не 403: не раскрываем существование чужих платежей
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Payment #{payment_id} not found")
        return payment

    async def list_user_payments(self, db: AsyncSession, user: CurrentUser) -> list[Payment]:
        stmt = select(Payment).where(Payment.user_id == user.id).order_by(Payment.created_at.desc(), Payment.id.desc())
        return list((await db.execute(stmt)).scalars().all())

    async def get_payment_by_secret(self, db: AsyncSession, payment_id: int, client_secret: str) -> Payment:
        payment = await self.get_payment(db, payment_id)
        if not payment.client_secret or not secrets.compare_digest(payment.client_secret, client_secret):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Payment #{payment_id} not found")
        return payment

    async def confirm_payment(
        self, db: AsyncSession, payment_id: int, payment_method_id: str = "pm_card_visa"
    ) -> Payment:
        # Блокировка строки: параллельные нажатия «Оплатить» не спишут деньги дважды
        payment = await self.get_payment(db, payment_id, for_update=True)

        if payment.status == PaymentStatus.SUCCEEDED.value:
            await db.rollback()
            return await self.get_payment(db, payment_id)

        if payment.status != PaymentStatus.PENDING.value:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot pay transaction in status {payment.status}",
            )

        res = await self.gateway.confirm_payment(
            provider_payment_id=payment.provider_payment_id or f"pi_{payment.id}",
            payment_method_id=payment_method_id,
        )

        if res.get("status") in ("succeeded", "SUCCEEDED", "success"):
            await self._mark_succeeded(db, payment, res.get("receipt_url") or payment.receipt_url)
        else:
            await self._mark_failed(db, payment, res.get("status"))

        return await self.get_payment(db, payment_id)

    async def handle_webhook(
        self, db: AsyncSession, raw_body: bytes, sig_header: str
    ) -> dict:
        event = self.gateway.verify_webhook(raw_body, sig_header)
        event_type = event.get("type") or event.get("event")

        if event_type in ("payment_intent.succeeded", "charge.succeeded"):
            obj = event.get("data", {}).get("object", {})
            payment = await self._find_payment_from_gateway_object(db, obj)
            if not payment:
                return {"status": "not_found"}

            charges = obj.get("charges", {}).get("data", [])
            new_receipt = charges[0].get("receipt_url") if charges else payment.receipt_url

            changed = await self._mark_succeeded(db, payment, new_receipt)
            return {"status": "confirmed" if changed else "already_processed"}

        if event_type == "payment_intent.payment_failed":
            obj = event.get("data", {}).get("object", {})
            payment = await self._find_payment_from_gateway_object(db, obj)
            if not payment:
                return {"status": "not_found"}
            changed = await self._mark_failed(db, payment, "payment_failed")
            return {"status": "failed" if changed else "already_processed"}

        return {"status": "acknowledged"}

    async def request_refund(
        self,
        db: AsyncSession,
        payment: Payment,
        reason: str,
        refund_amount: Optional[Decimal] = None,
    ) -> bool:
        """SUCCEEDED -> REFUND_PENDING. Возвращает False, если возврат уже начат или невозможен."""
        values = {
            "status": PaymentStatus.REFUND_PENDING.value,
            "refund_reason": reason[:255],
        }
        if refund_amount is not None:
            values["amount"] = refund_amount
        stmt = (
            update(Payment)
            .where(Payment.id == payment.id, Payment.status == PaymentStatus.SUCCEEDED.value)
            .values(**values)
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0

    async def process_refund(self, db: AsyncSession, payment_id: int) -> Payment:
        """
        Выполняет возврат в шлюзе для платежа в REFUND_PENDING.
        При сбое шлюза статус остаётся REFUND_PENDING — фоновый воркер повторит попытку.
        """
        payment = await self.get_payment(db, payment_id, for_update=True)
        if payment.status != PaymentStatus.REFUND_PENDING.value:
            await db.rollback()
            return await self.get_payment(db, payment_id)

        try:
            if payment.provider_payment_id:
                await self.gateway.refund(
                    payment.provider_payment_id,
                    amount=payment.amount,
                    reason=payment.refund_reason or "requested_by_customer",
                )
        except Exception:
            await db.rollback()
            logger.exception("Refund for payment %s failed, will retry", payment_id)
            return await self.get_payment(db, payment_id)

        payment.status = PaymentStatus.REFUNDED.value
        add_outbox_event(
            db,
            "payment.refunded",
            payment_event_payload(payment, reason=payment.refund_reason),
        )
        await db.commit()
        logger.info("Payment %s refunded", payment_id)
        return await self.get_payment(db, payment_id)

    async def refund_payment(
        self, db: AsyncSession, payment_id: int, reason: str = "admin_refund"
    ) -> Payment:
        payment = await self.get_payment(db, payment_id)

        if payment.status not in (PaymentStatus.SUCCEEDED.value, PaymentStatus.REFUND_PENDING.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only SUCCEEDED payments can be refunded (current: {payment.status})",
            )

        await self.request_refund(db, payment, reason)
        return await self.process_refund(db, payment_id)

    async def refund_for_booking(
        self,
        db: AsyncSession,
        booking_id: int,
        reason: str,
        refund_percentage: float = 1.0,
    ) -> Optional[Payment]:
        stmt = select(Payment).where(
            Payment.booking_id == booking_id,
            Payment.status.in_([PaymentStatus.SUCCEEDED.value, PaymentStatus.REFUND_PENDING.value]),
        )
        payment = (await db.execute(stmt)).scalars().first()
        if not payment:
            return None

        refund_amount = None
        if refund_percentage < 1.0:
            refund_amount = (payment.amount * Decimal(str(refund_percentage))).quantize(Decimal("0.01"))

        await self.request_refund(db, payment, reason, refund_amount=refund_amount)
        return await self.process_refund(db, payment.id)

    async def retry_pending_refunds(self, db: AsyncSession) -> int:
        stmt = select(Payment.id).where(Payment.status == PaymentStatus.REFUND_PENDING.value)
        payment_ids = list((await db.execute(stmt)).scalars().all())
        await db.rollback()

        refunded = 0
        for payment_id in payment_ids:
            payment = await self.process_refund(db, payment_id)
            if payment.status == PaymentStatus.REFUNDED.value:
                refunded += 1
        return refunded

    async def _mark_succeeded(self, db: AsyncSession, payment: Payment, receipt_url: Optional[str]) -> bool:
        # Атомарный переход: событие создаётся ровно один раз, даже при повторных вебхуках
        stmt = (
            update(Payment)
            .where(Payment.id == payment.id, Payment.status == PaymentStatus.PENDING.value)
            .values(status=PaymentStatus.SUCCEEDED.value, receipt_url=receipt_url)
        )
        result = await db.execute(stmt)
        if result.rowcount > 0:
            add_outbox_event(
                db,
                "payment.succeeded",
                # Формат из specification.json: { booking_id, user_id, amount }
                payment_event_payload(payment, receipt_url=receipt_url),
            )
        await db.commit()
        return result.rowcount > 0

    async def _mark_failed(self, db: AsyncSession, payment: Payment, gateway_status: Optional[str]) -> bool:
        stmt = (
            update(Payment)
            .where(Payment.id == payment.id, Payment.status == PaymentStatus.PENDING.value)
            .values(status=PaymentStatus.FAILED.value)
        )
        result = await db.execute(stmt)
        if result.rowcount > 0:
            add_outbox_event(
                db,
                "payment.failed",
                payment_event_payload(payment, gateway_status=gateway_status),
            )
        await db.commit()
        return result.rowcount > 0

    async def _find_payment_from_gateway_object(self, db: AsyncSession, obj: Dict[str, Any]) -> Optional[Payment]:
        payment_id = obj.get("metadata", {}).get("payment_id")
        provider_payment_id = obj.get("id")

        stmt = select(Payment)
        if payment_id:
            stmt = stmt.where(Payment.id == int(payment_id))
        elif provider_payment_id:
            stmt = stmt.where(Payment.provider_payment_id == provider_payment_id)
        else:
            return None
        return (await db.execute(stmt)).scalars().first()

    async def _get_by_idempotency_key(self, db: AsyncSession, idempotency_key: str) -> Optional[Payment]:
        stmt = select(Payment).where(Payment.idempotency_key == idempotency_key)
        return (await db.execute(stmt)).scalars().first()

    async def _get_active_for_booking(self, db: AsyncSession, booking_id: int) -> Optional[Payment]:
        stmt = select(Payment).where(
            Payment.booking_id == booking_id,
            Payment.status.in_(ACTIVE_STATUSES),
        )
        return (await db.execute(stmt)).scalars().first()

    @staticmethod
    def _check_idempotent_owner(payment: Payment, user: CurrentUser) -> Payment:
        if payment.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency-Key is already used by another request",
            )
        return payment

    @staticmethod
    def _resolve_active_payment(payment: Payment, user: CurrentUser) -> Payment:
        if payment.status != PaymentStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Booking has already been paid successfully",
            )
        if payment.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another user is currently completing payment for this booking",
            )
        # Повторный «Оплатить» по той же брони — возвращаем незавершённый платёж
        return payment


payment_service = PaymentService()
