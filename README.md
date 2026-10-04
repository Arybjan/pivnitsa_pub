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
- Pytest (pytest-asyncio)

## Структура проекта

```text
app/
  api/v1/payments.py          - эндпоинты инициализации, оплаты, вебхуков и чекаута
  api/v1/router.py            - объединение роутеров API v1
  core/config.py              - чтение настроек из .env
  core/database.py            - асинхронное подключение к PostgreSQL / SQLite
  core/security.py            - валидация JWT токенов пользователей
  models/payment.py           - модель таблицы payments со стейт-машиной статусов
  schemas/payment.py          - Pydantic-схемы запросов и ответов
  services/payment_service.py - бизнес-логика платежей, защита от гонок данных и идемпотентность
  services/stripe_gateway.py  - интеграция с платёжным шлюзом (Stripe / Test Mode)
  messaging/publisher.py      - публикация события payment.succeeded в events_exchange
  messaging/consumer.py       - слушатель booking.payment_rejected и booking.cancelled для авто-возвратов
  main.py                     - инициализация FastAPI, CORS и lifespan
alembic/                      - миграции базы данных
tests/                        - автоматические тесты (конкурентность, сквозная сага, вебхуки)
.env.example                  - шаблон переменных окружения
requirements.txt              - зависимости
Dockerfile                    - сборка контейнера
docker-compose.yml            - запуск сервиса и базы данных
```

## База данных

Таблица `payments` (строго по `specification.json`):
- `id`: BigInteger, primary key, autoincrement
- `booking_id`: BigInteger, foreign key (bookings.id), index, not null
- `user_id`: BigInteger, foreign key (users.id), index, not null
- `amount`: Numeric(12, 2), not null
- `currency`: String(10), default 'KGS', not null
- `status`: String(30), default 'PENDING' (`PENDING`, `SUCCEEDED`, `FAILED`, `REFUND_PENDING`, `REFUNDED`)
- `provider`: String(50), default 'STRIPE', not null
- `idempotency_key`: String(255), unique, index, nullable
- `provider_payment_id`: String(255), index, nullable
- `receipt_url`: String(500), nullable
- `created_at`: DateTime(timezone=True), default now()
- `updated_at`: DateTime(timezone=True), default now()

## Эндпоинты

- `POST /api/v1/payments` — Инициализация оплаты брони (поддерживает заголовок `Idempotency-Key`).
- `GET /api/v1/payments/{id}` — Получение статуса платежа и ссылки на электронный чек.
- `POST /api/v1/payments/{id}/pay` — Подтверждение оплаты токенизированной картой.
- `POST /api/v1/payments/{id}/refund` — Инициализация возврата средств.
- `POST /api/v1/payments/webhook` — Приём вебхуков от платёжного шлюза с крипто-подписью.
- `GET /api/v1/payments/{id}/checkout` — Интерактивная мобильная веб-страничка чекаута для демонстрации на ревью.
- `GET /health` — Проверка состояния микросервиса.

## Безопасность и архитектурные гарантии

1. **PCI-DSS Compliance:** Сервер никогда не принимает и не сохраняет полные номера карт (PAN) или CVV. Оплата токенизируется через шлюз.
2. **Защита от Double-Spend:** Защита от конкурентной оплаты одного столика несколькими пользователями (отсечение с HTTP 409 Conflict).
3. **Идемпотентность вебхуков:** Атомарные переходы состояний (`update ... where status='PENDING'`) гарантируют, что повторные вебхуки от банка не создают дубликаты событий в RabbitMQ.

## Запуск

1. Создать файл `.env` (на основе `.env.example`):
```env
PORT=8004
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/payment_db
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
RABBITMQ_EXCHANGE=events_exchange
PAYMENT_GATEWAY_ENV=sandbox
STRIPE_SECRET_KEY=sk_test_placeholder_for_dev
```

2. Установить зависимости:
```bash
pip install -r requirements.txt
```

3. Применить миграции:
```bash
alembic upgrade head
```

4. Запустить сервис:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8004 --reload
```

5. Запустить тесты:
```bash
pytest -v
```

Документация Swagger доступна по адресу: `http://127.0.0.1:8004/docs`
Интерактивный экран оплаты: `http://127.0.0.1:8004/api/v1/payments/{id}/checkout`
