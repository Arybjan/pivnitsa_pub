# Notification Microservice

Микросервис уведомлений и отправки SMS.

## Стек технологий

- Python 3.12+
- FastAPI
- Uvicorn
- SQLAlchemy 2.0 (async)
- asyncpg
- Alembic
- Pydantic v2 / pydantic-settings
- HTTPX
- Pytest / Respx

## Структура проекта

```text
app/
  api/v1/notifications.py - эндпоинты уведомлений и SMS
  core/config.py          - чтение настроек из .env
  core/database.py        - подключение к базе данных
  models/notification.py  - модель таблицы notifications
  schemas/base.py         - базовые типы (BigIntId) и валидация
  schemas/notification.py - схемы запросов и ответов
  services/sms_service.py - отправка SMS через XML API Nikita
  main.py                 - запуск приложения
alembic/                  - файлы миграций базы данных
tests/                    - автоматические тесты (55 тестов)
specification.json        - спецификация архитектуры и схемы БД
.env                      - переменные окружения
.env.example              - пример переменных окружения
requirements.txt          - зависимости
```

## База данных

Таблица `notifications`:
- `id`: BigInteger, primary key
- `user_id`: BigInteger, index
- `title`: String(255)
- `message`: Text
- `type`: String(30)
- `related_event_id`: BigInteger, nullable
- `related_booking_id`: BigInteger, nullable
- `is_read`: Boolean, default false
- `created_at`: DateTime, default now()

## Эндпоинты

- `POST /api/v1/notifications/` — Создание уведомления.
- `GET /api/v1/notifications/` — Список уведомлений пользователя (user_id, unread_only, limit, offset).
- `GET /api/v1/notifications/unread-count` — Количество непрочитанных уведомлений (user_id).
- `PATCH /api/v1/notifications/{notification_id}/read` — Пометить одно уведомление как прочитанное.
- `PATCH /api/v1/notifications/read-all` — Пометить все уведомления пользователя как прочитанные (user_id).
- `POST /api/v1/notifications/sms` — Отправка SMS через провайдер Nikita в фоне (phone_number, message).
- `GET /health` — Проверка работы сервиса.

## Запуск

1. Создать файл `.env` (на основе `.env.example`):
```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/notifications_db
NIKITA_API_URL=https://smspro.nikita.kg/api/message
NIKITA_LOGIN=your_login
NIKITA_PASSWORD=your_password
NIKITA_SENDER=YOUR_SENDER_NAME
NIKITA_TEST_MODE=true
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
uvicorn app.main:app --reload
```

5. Запустить тесты:
```bash
pytest -v tests/
```

Документация Swagger доступна по адресу: `http://127.0.0.1:8000/docs`
