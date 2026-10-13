# Payment Microservice

Микросервис обработки онлайн-платежей и возвратов для бронирования столиков Pivnitsa Pub.
Реализует требования эпика **E6** бэклога: **US-24** (онлайн-оплата картой по стандарту PCI-DSS), **US-25** (электронные квитанции и чеки) и **US-26** (автоматический возврат средств при отмене брони).

## Стек технологий

- Python 3.12+
- FastAPI
- Uvicorn
- SQLAlchemy 2.0 (async)
- asyncpg / aiosqlite
- Alembic
- Pydantic v2 / pydantic-settings
- Stripe SDK / Адаптер эквайринга
- RabbitMQ (aio-pika)
- PyJWT
- HTTPX (запросы к Booking Service)
- Pytest (pytest-asyncio)

## Структура проекта

```text
app/
  api/v1/payments.py          - эндпоинты оплаты, возвратов, вебхуков и страницы чекаута
  api/v1/router.py            - объединение роутеров API v1
  core/config.py              - чтение настроек из .env
  core/database.py            - асинхронное подключение к PostgreSQL / SQLite
  core/security.py            - проверка JWT (exp обязателен), роли admin/owner
  models/payment.py           - таблицы payments и outbox_events
  schemas/payment.py          - Pydantic-схемы запросов и ответов
  services/payment_service.py - бизнес-логика платежей, идемпотентность, возвраты
  services/booking_client.py  - чтение брони из Booking Service (владелец, статус, гости)
  services/stripe_gateway.py  - интеграция с платёжным шлюзом (Stripe / Test Mode)
  messaging/connection.py     - подключение к RabbitMQ с повторными попытками
  messaging/publisher.py      - публикация событий в events_exchange
  messaging/consumer.py       - слушатель booking.payment_rejected и booking.cancelled для авто-возвратов
  messaging/workers.py        - отправка outbox и повтор неудавшихся возвратов
  main.py                     - инициализация FastAPI, CORS и lifespan
alembic/                      - миграции базы данных (единственный способ создать схему)
tests/                        - автотесты на базе, созданной миграциями
```

## Как проходит оплата

1. Гость создаёт бронь в Booking Service — статус `PENDING_PAYMENT`, стол держится 15 минут.
2. `POST /api/v1/payments {"booking_id": ...}` с токеном гостя. Payment Service запрашивает бронь
   в Booking Service **токеном гостя** и проверяет: бронь его, статус `PENDING_PAYMENT`, время не вышло.
3. Сумма считается на сервере: `DEPOSIT_PER_GUEST × guests`. Сумму и `user_id` из запроса сервис не принимает.
4. Гость платит: `POST /api/v1/payments/{id}/pay` с токеном или со страницы чекаута по `client_secret`.
5. Статус `SUCCEEDED` и событие `payment.succeeded` записываются **в одной транзакции** (outbox).
   Фоновый воркер отправляет событие в RabbitMQ; если брокер недоступен, событие дождётся отправки.
6. Booking Service получает `payment.succeeded` и подтверждает бронь (`booking.confirmed`).

Если оплата пришла, а бронь уже сгорела или отменена, Booking Service присылает `booking.payment_rejected`,
и сервис автоматически делает возврат. Так же возвращаются деньги при `booking.cancelled` с `previous_status: CONFIRMED`.

## База данных

Таблица `payments` (по `specification.json` + служебные поля):
- `id`: BigInteger, primary key, autoincrement
- `booking_id`: BigInteger, index, not null
- `user_id`: BigInteger, index, not null
- `amount`: Numeric(12, 2), not null
- `currency`: String(10), default 'KGS', not null
- `status`: String(30) — `PENDING`, `SUCCEEDED`, `FAILED`, `REFUND_PENDING`, `REFUNDED`
- `provider`: String(50), not null
- `idempotency_key`: String(255), unique
- `provider_payment_id`: String(255), index
- `client_secret`: String(255) — секрет страницы оплаты, выдаётся только владельцу
- `receipt_url`: String(500)
- `refund_reason`: String(255)
- `created_at`, `updated_at`: DateTime(timezone=True)

Уникальный индекс `uq_payments_active_booking`: на одну бронь не больше одного платежа
в статусах `PENDING` / `SUCCEEDED` / `REFUND_PENDING` — защита от двойной оплаты на уровне БД.

Таблица `outbox_events`: события, ожидающие отправки в RabbitMQ.

## Эндпоинты

| Метод | Путь | Доступ | Описание |
|---|---|---|---|
| POST | `/api/v1/payments` | гость (токен) | Создать платёж по брони. Тело: `{"booking_id"}`. Заголовок `Idempotency-Key` — защита от двойного клика |
| GET | `/api/v1/payments/my` | гость | Мои платежи и чеки (US-25) |
| GET | `/api/v1/payments/{id}` | владелец / admin | Статус платежа |
| POST | `/api/v1/payments/{id}/pay` | владелец или `X-Client-Secret` | Оплата токенизированной картой |
| POST | `/api/v1/payments/{id}/refund` | admin / owner | Возврат |
| POST | `/api/v1/payments/webhook` | подпись шлюза | Вебхук. Без подписи принимается только в `sandbox` |
| GET | `/api/v1/payments/{id}/checkout?secret=...` | по секрету | Страница оплаты для демонстрации |
| GET | `/health`, `/health/ready` | — | Живость и готовность (БД, RabbitMQ, очередь outbox) |

## События RabbitMQ (`events_exchange`)

| Публикует | Ключ | Поля |
|---|---|---|
| ✅ | `payment.succeeded` | `payment_id, booking_id, user_id, amount, currency, receipt_url` |
| ✅ | `payment.failed` | `payment_id, booking_id, user_id, amount, currency, gateway_status` |
| ✅ | `payment.refunded` | `payment_id, booking_id, user_id, amount, currency, reason` |

| Слушает | Ключ | Действие |
|---|---|---|
| ✅ | `booking.payment_rejected` | возврат оплаты |
| ✅ | `booking.cancelled` с `previous_status: CONFIRMED` | возврат оплаты |

## Запуск

1. Создать файл `.env` на основе `.env.example`. `JWT_SECRET` должен совпадать с Auth и Booking Service.

2. Запустить вместе с Booking Service (RabbitMQ берётся из его docker-compose):
```bash
docker compose up -d --build
```
Миграции применяются при старте контейнера.

3. Локально без Docker:
```bash
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8004 --reload
```

4. Тесты:
```bash
pytest -v
```

Документация Swagger: `http://127.0.0.1:8004/docs`
