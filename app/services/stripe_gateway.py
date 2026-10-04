import logging
import uuid
from decimal import Decimal
from typing import Any, Dict, Optional
import stripe
from app.core.config import settings

logger = logging.getLogger(__name__)

class StripePaymentGateway:
    def __init__(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        self.is_sandbox = (
            settings.PAYMENT_GATEWAY_ENV == "sandbox"
            or not settings.STRIPE_SECRET_KEY
            or "placeholder" in settings.STRIPE_SECRET_KEY
        )

    async def create_intent(
        self,
        payment_id: int,
        amount: Decimal,
        currency: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        meta = metadata or {}
        meta["payment_id"] = str(payment_id)

        if self.is_sandbox:
            fake_id = f"pi_sim_{payment_id}_{uuid.uuid4().hex[:8]}"
            return {
                "id": fake_id,
                "client_secret": f"{fake_id}_secret_{uuid.uuid4().hex[:12]}",
                "status": "requires_payment_method",
                "amount": int(amount * 100),
                "currency": currency.lower(),
                "receipt_url": f"https://pay.pivnitsa.kg/receipts/{payment_id}",
            }

        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),
                currency=currency.lower(),
                description=description,
                metadata=meta,
                automatic_payment_methods={"enabled": True},
            )
            return {
                "id": intent.id,
                "client_secret": intent.client_secret,
                "status": intent.status,
                "amount": intent.amount,
                "currency": intent.currency,
                "receipt_url": getattr(intent, "receipt_url", None),
            }
        except stripe.StripeError as e:
            logger.error("Stripe intent error: %s", e)
            raise

    async def confirm_payment(
        self,
        provider_payment_id: str,
        payment_method_id: str = "pm_card_visa",
    ) -> Dict[str, Any]:
        if self.is_sandbox or provider_payment_id.startswith("pi_sim_"):
            return {
                "id": provider_payment_id,
                "status": "succeeded",
                "receipt_url": f"https://pay.pivnitsa.kg/receipts/{provider_payment_id}",
            }

        try:
            intent = stripe.PaymentIntent.confirm(
                provider_payment_id,
                payment_method=payment_method_id,
                return_url="https://pay.pivnitsa.kg/complete",
            )
            charges = getattr(intent, "charges", None)
            receipt_url = None
            if charges and charges.data:
                receipt_url = charges.data[0].receipt_url
            return {
                "id": intent.id,
                "status": intent.status,
                "receipt_url": receipt_url,
            }
        except stripe.StripeError as e:
            logger.error("Stripe confirm error: %s", e)
            raise

    async def refund(
        self,
        provider_payment_id: str,
        amount: Optional[Decimal] = None,
        reason: str = "requested_by_customer",
    ) -> Dict[str, Any]:
        if self.is_sandbox or provider_payment_id.startswith("pi_sim_"):
            return {
                "id": f"re_sim_{uuid.uuid4().hex[:10]}",
                "status": "succeeded",
                "amount": int(amount * 100) if amount else None,
            }

        try:
            refund_args = {
                "payment_intent": provider_payment_id,
                "reason": reason,
            }
            if amount:
                refund_args["amount"] = int(amount * 100)
            rf = stripe.Refund.create(**refund_args)
            return {
                "id": rf.id,
                "status": rf.status,
            }
        except stripe.StripeError as e:
            logger.error("Stripe refund error: %s", e)
            raise

    def verify_webhook(self, payload: bytes, signature_header: str) -> Dict[str, Any]:
        if self.is_sandbox or "placeholder" in settings.STRIPE_WEBHOOK_SECRET:
            import json
            try:
                return json.loads(payload.decode("utf-8"))
            except Exception:
                return {}

        try:
            event = stripe.Webhook.construct_event(
                payload, signature_header, settings.STRIPE_WEBHOOK_SECRET
            )
            return event
        except Exception as e:
            logger.error("Webhook signature verification failed: %s", e)
            raise

gateway = StripePaymentGateway()
