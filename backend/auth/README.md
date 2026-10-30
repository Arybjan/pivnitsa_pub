# Auth / Users Service

Микросервис регистрации, входа и профилей пользователей (эпик E2: US-03…US-07).
Выпускает JWT, который принимают Booking, Payment, Event и Notification Service.

## Стек технологий

- Python 3.12+, FastAPI, Uvicorn
- SQLAlchemy 2.0 (async), asyncpg, Alembic
- Redis — OTP-коды, refresh-сессии, защита от перебора
- PyJWT, bcrypt
- Pytest, fakeredis, respx

## Структура проекта

```text
app/
  api/deps.py              - зависимости: текущий пользователь, проверка роли admin
  api/v1/auth.py           - регистрация, вход, OTP, refresh, выход, сброс пароля
  api/v1/users.py          - профиль /users/me и админские эндпоинты
  core/config.py           - настройки из .env
  core/database.py         - подключение к PostgreSQL
  core/redis.py            - подключение к Redis
  core/roles.py            - роли user / admin / owner
  core/security.py         - JWT и хеширование паролей
  models/user.py           - таблицы users и profiles
  schemas/                 - схемы запросов и ответов, нормализация телефона
  services/auth_service.py - логика регистрации, входа и токенов
  services/otp_service.py  - выдача и проверка SMS-кодов
  services/session_store.py- активные refresh-токены
  services/sms_sender.py   - отправка SMS (лог или Notification Service)
  services/user_service.py - профиль, смена пароля, управление пользователями
  cli.py                   - служебные команды (назначение роли)
  main.py                  - запуск приложения
alembic/                   - миграции
tests/                     - автотесты
```

## База данных

`users`: `id` BigInteger PK, `phone` String(20) unique, `email` String(255) unique nullable,
`password_hash`, `role` (`user` / `admin` / `owner`), `is_active`, `created_at`, `updated_at`.

`profiles` (1:1 с users): `user_id` FK unique, `first_name`, `last_name`, `avatar_url`, `created_at`, `updated_at`.

## Как работает вход

Регистрация (US-03) — три шага:

1. `POST /api/v1/auth/otp/send` `{"phone": "+996555123456", "purpose": "register"}` — SMS с 6-значным кодом.
2. `POST /api/v1/auth/otp/verify` `{"phone": "...", "code": "123456", "purpose": "register"}` → `verification_token` (одноразовый, 10 минут).
3. `POST /api/v1/auth/register` `{"verification_token": "...", "password": "secret123", "first_name": "...", "email": "..."}` → токены и профиль.

Вход (US-04): `POST /api/v1/auth/login` с `{"phone", "password"}` **или** с `{"verification_token"}`,
полученным через OTP с `purpose: "login"`.

Номер можно вводить в любом виде (`0555 12-34-56`, `996555123456`) — он приводится к `+996555123456`.

Пошаговая инструкция с примерами запросов и ошибками: [docs/REGISTRATION.md](docs/REGISTRATION.md).

## Эндпоинты

Auth:
- `POST /api/v1/auth/otp/send` — отправить SMS-код (`register` / `login` / `reset_password`).
- `POST /api/v1/auth/otp/verify` — проверить код, получить `verification_token`.
- `POST /api/v1/auth/register` — регистрация.
- `POST /api/v1/auth/login` — вход по паролю или по SMS-коду.
- `POST /api/v1/auth/refresh` — новая пара токенов; старый refresh становится недействительным.
- `POST /api/v1/auth/logout` — выход на текущем устройстве (US-06).
- `POST /api/v1/auth/logout-all` — выход на всех устройствах.
- `POST /api/v1/auth/password/reset` — новый пароль по `verification_token` (`reset_password`).

Users:
- `GET /api/v1/users/me` — мой профиль (US-05).
- `PATCH /api/v1/users/me` — изменить имя, фамилию, email, аватар (US-05).
- `POST /api/v1/users/me/password` — сменить пароль.
- `DELETE /api/v1/users/me` — удалить аккаунт (US-07): аккаунт деактивируется, сессии завершаются.
- `GET /api/v1/users` — список пользователей с фильтрами `role`, `is_active`, `phone` (admin).
- `GET /api/v1/users/{id}` — пользователь по ID (admin).
- `PATCH /api/v1/users/{id}` — заблокировать / разблокировать (admin), сменить роль (только owner).
- `GET /health` — состояние сервиса, БД и Redis.

Документация Swagger: `http://localhost:8001/docs`.

## JWT — контракт для остальных сервисов

Access-токен (15 минут) подписан общим `JWT_SECRET`, алгоритм HS256:

```json
{
  "sub": "42",
  "role": "user",
  "phone": "+996555123456",
  "is_active": true,
  "type": "access",
  "token_type": "access",
  "iat": 1760000000,
  "exp": 1760000900,
  "jti": "..."
}
```

- `sub` — ID пользователя (BigInteger) строкой: `int(payload["sub"])`.
- `role` — `user`, `admin` или `owner`. Админские права: `role in ("admin", "owner")`.
- Refresh- и verification-токены подписаны другим ключом (выводится из `JWT_SECRET`),
  поэтому другие сервисы не примут их вместо access-токена.

## Безопасность

- Пароль: минимум 8 символов, буква и цифра; хранится в bcrypt.
- OTP: в Redis хранится только HMAC кода; 5 минут жизни, повторная отправка не чаще раза в минуту,
  не больше 5 SMS в час на номер, 5 попыток ввода — потом код сгорает.
- Вход: после 5 неверных паролей номер блокируется на 15 минут. Ответ для «нет такого номера»
  и «неверный пароль» одинаковый.
- Refresh-токены одноразовые (rotation). Повторное использование старого токена завершает все сессии.
- Смена пароля, сброс пароля, блокировка и смена роли завершают все сессии пользователя.

## Запуск

1. Создать `.env` из `.env.example` и задать `JWT_SECRET` — такой же, как у остальных сервисов.
2. Запуск в Docker (миграции применяются автоматически):
```bash
docker compose up --build
```
3. Без Docker (нужны PostgreSQL и Redis):
```bash
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8001
```

При `SMS_PROVIDER=console` код печатается в лог сервиса, а при `OTP_EXPOSE_IN_RESPONSE=true`
(не в production) ещё и возвращается в ответе `/otp/send` в поле `debug_code` — удобно для фронтенда.
Для реальной отправки: `SMS_PROVIDER=notification` и `NOTIFICATION_SERVICE_URL`.

Назначить первого владельца (после его регистрации):
```bash
docker compose exec auth-service python -m app.cli set-role +996555123456 owner
```

## Тесты

```bash
pytest
```

Тестам не нужны PostgreSQL и Redis: используются SQLite в памяти и fakeredis.
