# Payment Service (Pivnitsa Pub)

PCI-DSS compliant payment processing microservice for table reservations in Pivnitsa Pub.
Implements user stories **US-24** (online payments), **US-25** (receipts & invoices), and **US-26** (automatic refunds on cancellation).

## Architecture & Features

- **Payment Gateway:** Stripe / Payment Adapter with tokenized payment method support (PCI-DSS: server never stores raw card credentials).
- **Interactive Checkout:** Web checkout endpoint `/api/v1/payments/{id}/checkout` for mobile and live review demonstrations.
- **Concurrency & Idempotency:**
  - Idempotency-Key support on payment creation.
  - Per-booking concurrency guard preventing simultaneous double-spend across multiple users.
  - Atomic transitions ensuring duplicate webhook delivery from gateway publishes event exactly once.
- **Event-Driven Choreography (RabbitMQ):**
  - Publishes `payment.succeeded` to `events_exchange` when payment completes (triggers Booking confirmation and SMS notifications).
  - Listens for `booking.payment_rejected` and `booking.cancelled` to issue automatic refunds.

## Endpoints

| Method | Path | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/payments` | Initiate payment for booking (returns checkout URL & client secret) |
| `GET` | `/api/v1/payments/{id}` | Get payment status and details |
| `POST` | `/api/v1/payments/{id}/pay` | Confirm payment with tokenized card |
| `POST` | `/api/v1/payments/{id}/refund` | Initiate refund |
| `POST` | `/api/v1/payments/webhook` | Cryptographically verified gateway webhook receiver |
| `GET` | `/api/v1/payments/{id}/checkout` | Interactive HTML mobile checkout page |
| `GET` | `/health` | Health check endpoint |

## Running Locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run migrations
alembic upgrade head

# 3. Start server
uvicorn app.main:app --port 8004 --reload
```

## Running Tests

```bash
pytest -v
```
