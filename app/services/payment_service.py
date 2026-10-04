import asyncio
import logging
from decimal import Decimal
from typing import Dict, Optional
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.payment import Payment, PaymentStatus
from app.schemas.payment import PaymentCreate
from app.services.stripe_gateway import gateway
from app.messaging.publisher import publisher

logger = logging.getLogger(__name__)

_booking_locks: Dict[int, asyncio.Lock] = {}
_locks_guard = asyncio.Lock()

async def _get_booking_lock(booking_id: int) -> asyncio.Lock:
    async with _locks_guard:
        if booking_id not in _booking_locks:
            _booking_locks[booking_id] = asyncio.Lock()
        return _booking_locks[booking_id]

class PaymentService:
    async def create_payment(
        self,
        db: AsyncSession,
        data: PaymentCreate,
        resolved_user_id: int,
        idempotency_key: Optional[str] = None,
    ) -> Payment:
        # Acquire lock for this booking to prevent concurrent double-spend
        lock = await _get_booking_lock(data.booking_id)
        async with lock:
            # 1. Idempotency Key check
            if idempotency_key:
                stmt = select(Payment).where(Payment.idempotency_key == idempotency_key)
                existing = (await db.execute(stmt)).scalars().first()
                if existing:
                    existing.checkout_url = f"/api/v1/payments/{existing.id}/checkout"
                    return existing

            # 2. Check if booking is already successfully paid
            stmt = select(Payment).where(
                Payment.booking_id == data.booking_id,
                Payment.status == PaymentStatus.SUCCEEDED.value,
            )
            existing_paid = (await db.execute(stmt)).scalars().first()
            if existing_paid:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Booking has already been paid successfully",
                )

            # 3. Check if there is an active PENDING payment for this booking
            stmt = select(Payment).where(
                Payment.booking_id == data.booking_id,
                Payment.status == PaymentStatus.PENDING.value,
            )
            existing_pending = (await db.execute(stmt)).scalars().first()
            if existing_pending:
                if existing_pending.user_id != resolved_user_id:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Another user is currently completing payment for this booking",
                    )
                existing_pending.checkout_url = f"/api/v1/payments/{existing_pending.id}/checkout"
                return existing_pending

            payment = Payment(
                booking_id=data.booking_id,
                user_id=resolved_user_id,
                amount=data.amount,
                currency=data.currency.upper(),
                status=PaymentStatus.PENDING.value,
                provider=data.provider.upper(),
                idempotency_key=idempotency_key,
            )
            try:
                db.add(payment)
                await db.flush()
            except IntegrityError:
                await db.rollback()
                if idempotency_key:
                    stmt = select(Payment).where(Payment.idempotency_key == idempotency_key)
                    existing = (await db.execute(stmt)).scalars().first()
                    if existing:
                        existing.checkout_url = f"/api/v1/payments/{existing.id}/checkout"
                        return existing
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Conflict occurred while processing payment",
                )

            intent = await gateway.create_intent(
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

            payment.client_secret = intent.get("client_secret")
            payment.checkout_url = f"/api/v1/payments/{payment.id}/checkout"
            return payment

    async def get_payment(self, db: AsyncSession, payment_id: int) -> Payment:
        stmt = select(Payment).where(Payment.id == payment_id)
        payment = (await db.execute(stmt)).scalars().first()
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment #{payment_id} not found",
            )
        payment.checkout_url = f"/api/v1/payments/{payment.id}/checkout"
        return payment

    async def confirm_payment(
        self, db: AsyncSession, payment_id: int, payment_method_id: str = "pm_card_visa"
    ) -> Payment:
        payment = await self.get_payment(db, payment_id)

        if payment.status == PaymentStatus.SUCCEEDED.value:
            return payment

        if payment.status != PaymentStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot pay transaction in status {payment.status}",
            )

        res = await gateway.confirm_payment(
            provider_payment_id=payment.provider_payment_id or f"pi_{payment.id}",
            payment_method_id=payment_method_id,
        )

        if res.get("status") in ("succeeded", "SUCCEEDED", "success"):
            # Atomic update: only update and emit if current status is PENDING
            stmt = (
                update(Payment)
                .where(Payment.id == payment_id, Payment.status == PaymentStatus.PENDING.value)
                .values(
                    status=PaymentStatus.SUCCEEDED.value,
                    receipt_url=res.get("receipt_url") or payment.receipt_url,
                )
            )
            upd_res = await db.execute(stmt)
            await db.commit()

            if upd_res.rowcount > 0:
                # Exactly one coroutine flips status and emits event
                await publisher.publish(
                    routing_key="payment.succeeded",
                    payload={
                        "booking_id": payment.booking_id,
                        "user_id": payment.user_id,
                        "amount": str(payment.amount),
                    },
                )
        else:
            stmt = (
                update(Payment)
                .where(Payment.id == payment_id, Payment.status == PaymentStatus.PENDING.value)
                .values(status=PaymentStatus.FAILED.value)
            )
            await db.execute(stmt)
            await db.commit()

        return await self.get_payment(db, payment_id)

    async def handle_webhook(
        self, db: AsyncSession, raw_body: bytes, sig_header: str
    ) -> dict:
        event = gateway.verify_webhook(raw_body, sig_header)
        event_type = event.get("type") or event.get("event")

        # Standard Stripe webhook format
        if event_type in ("payment_intent.succeeded", "charge.succeeded"):
            obj = event.get("data", {}).get("object", {})
            provider_payment_id = obj.get("id")
            meta = obj.get("metadata", {})
            payment_id_str = meta.get("payment_id")

            stmt = select(Payment)
            if payment_id_str:
                stmt = stmt.where(Payment.id == int(payment_id_str))
            elif provider_payment_id:
                stmt = stmt.where(Payment.provider_payment_id == provider_payment_id)
            else:
                return {"status": "ignored"}

            payment = (await db.execute(stmt)).scalars().first()
            if not payment:
                return {"status": "not_found"}

            charges = obj.get("charges", {}).get("data", [])
            new_receipt = charges[0].get("receipt_url") if charges else payment.receipt_url

            # Atomic transition PENDING -> SUCCEEDED
            upd_stmt = (
                update(Payment)
                .where(Payment.id == payment.id, Payment.status == PaymentStatus.PENDING.value)
                .values(status=PaymentStatus.SUCCEEDED.value, receipt_url=new_receipt)
            )
            upd_res = await db.execute(upd_stmt)
            await db.commit()

            if upd_res.rowcount > 0:
                await publisher.publish(
                    routing_key="payment.succeeded",
                    payload={
                        "booking_id": payment.booking_id,
                        "user_id": payment.user_id,
                        "amount": str(payment.amount),
                    },
                )
                return {"status": "confirmed"}
            return {"status": "already_processed"}

        # Generic webhook format (for simulated or alternative gateways)
        if event.get("status") in ("SUCCESS", "succeeded", "SUCCEEDED"):
            p_id = event.get("payment_id") or event.get("order_id")
            if p_id:
                stmt = select(Payment).where(Payment.id == int(p_id))
                payment = (await db.execute(stmt)).scalars().first()
                if payment:
                    upd_stmt = (
                        update(Payment)
                        .where(Payment.id == payment.id, Payment.status == PaymentStatus.PENDING.value)
                        .values(status=PaymentStatus.SUCCEEDED.value)
                    )
                    upd_res = await db.execute(upd_stmt)
                    await db.commit()

                    if upd_res.rowcount > 0:
                        await publisher.publish(
                            routing_key="payment.succeeded",
                            payload={
                                "booking_id": payment.booking_id,
                                "user_id": payment.user_id,
                                "amount": str(payment.amount),
                            },
                        )
                        return {"status": "confirmed"}
                    return {"status": "already_processed"}

        return {"status": "acknowledged"}

    async def refund_payment(
        self, db: AsyncSession, payment_id: int, reason: str = "user_cancellation"
    ) -> Payment:
        payment = await self.get_payment(db, payment_id)

        if payment.status != PaymentStatus.SUCCEEDED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only SUCCEEDED payments can be refunded (current: {payment.status})",
            )

        if payment.provider_payment_id:
            await gateway.refund(payment.provider_payment_id, amount=payment.amount, reason=reason)

        payment.status = PaymentStatus.REFUNDED.value
        await db.commit()
        await db.refresh(payment)
        return payment

payment_service = PaymentService()
