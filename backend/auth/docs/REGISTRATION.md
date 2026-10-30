# Регистрация в Pivnitsa: инструкция

Регистрация в Auth Service — это три запроса: отправить SMS-код, подтвердить его, создать аккаунт с паролем.
В ответ на последний запрос приходит `access_token`, с ним работают все остальные сервисы.

1. `POST /api/v1/auth/otp/send` — отправить код на телефон.
2. `POST /api/v1/auth/otp/verify` — проверить код, получить `verification_token`.
3. `POST /api/v1/auth/register` — создать аккаунт, получить токены.

| Что | Где |
| --- | --- |
| Адрес сервиса (локально) | `http://localhost:8001` |
| Swagger для ручной проверки | `http://localhost:8001/docs` |
| Формат запросов | JSON, заголовок `Content-Type: application/json` |

## Шаг 1. Отправить SMS-код

`POST /api/v1/auth/otp/send` отправляет на номер 6-значный код, который живёт 5 минут.

```json
{
  "phone": "0705072003",
  "purpose": "register"
}
```

Ответ `200`:

```json
{
  "message": "If the number is valid, a code has been sent",
  "expires_in": 300,
  "resend_after": 60,
  "debug_code": "519966"
}
```

- Номер можно писать в любом виде: `0705072003`, `705072003`, `+996 705 07-20-03`. Сервис приводит его к `+996705072003`.
- `purpose` для регистрации — `register` (значение по умолчанию). Для входа по SMS — `login`, для сброса пароля — `reset_password`.
- `resend_after: 60` — новый код можно запросить через 60 секунд. Не больше 5 кодов в час на один номер.
- `debug_code` приходит только в режиме разработки. В production его нет, код приходит только по SMS.

## Шаг 2. Подтвердить код

`POST /api/v1/auth/otp/verify` проверяет код и возвращает `verification_token` — доказательство того, что номер принадлежит пользователю.

```json
{
  "phone": "0705072003",
  "code": "519966",
  "purpose": "register"
}
```

Ответ `200`:

```json
{
  "verification_token": "eyJhbGciOiJIUzI1NiIs...",
  "expires_in": 600
}
```

- `phone` и `purpose` — те же, что в шаге 1.
- На ввод кода даётся 5 попыток. После пятой ошибки код сгорает, нужно запросить новый.
- `verification_token` действует 10 минут и срабатывает один раз.

## Шаг 3. Создать аккаунт

`POST /api/v1/auth/register` создаёт пользователя с ролью `user` и сразу возвращает токены — отдельно входить не нужно.

```json
{
  "verification_token": "eyJhbGciOiJIUzI1NiIs...",
  "password": "Atai1234",
  "first_name": "Atai",
  "last_name": "Samudinov",
  "email": "user@example.com"
}
```

| Поле | Обязательное | Правила |
| --- | --- | --- |
| `verification_token` | да | из шага 2, `purpose: register` |
| `password` | да | 8–72 символа, хотя бы одна буква и одна цифра |
| `first_name` | нет | до 100 символов |
| `last_name` | нет | до 100 символов |
| `email` | нет | корректный email, не занятый другим пользователем |

Ответ `201`:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 900,
  "user": {
    "id": 2,
    "phone": "+996705072003",
    "email": "user@example.com",
    "role": "user",
    "is_active": true,
    "first_name": "Atai",
    "last_name": "Samudinov",
    "avatar_url": null,
    "created_at": "2026-10-13T14:07:16.630475Z"
  }
}
```

## После регистрации

Во всех запросах, где нужна авторизация, передавайте `access_token` в заголовке:

```
Authorization: Bearer <access_token>
```

Этот же токен принимают Booking, Payment и Notification Service — входить в каждый отдельно не нужно.

| Задача | Запрос | Тело |
| --- | --- | --- |
| Проверить, что токен работает | `GET /api/v1/users/me` | — |
| Обновить токен (access живёт 15 минут) | `POST /api/v1/auth/refresh` | `{"refresh_token": "..."}` |
| Войти по паролю | `POST /api/v1/auth/login` | `{"phone": "0705072003", "password": "Atai1234"}` |
| Войти по SMS | `POST /api/v1/auth/login` | `{"verification_token": "..."}` с `purpose: login` |
| Выйти | `POST /api/v1/auth/logout` | `{"refresh_token": "..."}` |

- `refresh_token` живёт 30 дней и срабатывает один раз: после `/refresh` сохраняйте новую пару токенов.
- Повторное использование старого `refresh_token` завершает все сессии пользователя.
- Роль приходит в `user.role`: `user`, `admin` или `owner`. В админ-панель пускать только `admin` и `owner`.

## Ошибки

Все ошибки приходят в виде `{"detail": "..."}`. Показывайте пользователю свой текст по коду ответа.

| Код | Шаг | `detail` | Что делать |
| --- | --- | --- | --- |
| 409 | 1 | Phone number is already registered | Номер уже зарегистрирован — предложить войти |
| 429 | 1 | Code was sent recently, try again later | Ждать столько секунд, сколько в заголовке `Retry-After` |
| 429 | 1 | Too many codes requested, try again later | Лимит 5 кодов в час — ждать `Retry-After` |
| 503 | 1 | SMS delivery is temporarily unavailable | SMS-сервис не ответил — повторить сразу |
| 400 | 2 | Invalid code | Код неверный — ввести заново |
| 400 | 2 | Code expired or not requested | Код истёк или другой номер/`purpose` — запросить новый |
| 429 | 2 | Too many invalid attempts, request a new code | 5 ошибок — запросить новый код |
| 401 | 3 | Invalid or expired verification token | Прошло 10 минут — начать с шага 1 |
| 401 | 3 | Verification token already used | Токен уже потрачен — начать с шага 1 |
| 409 | 3 | Email is already in use | Указать другой email или оставить пустым |
| 422 | любой | список полей с ошибками | Неверный номер, слабый пароль, лишнее поле или сломанный JSON |

## Проверка в Swagger

В режиме разработки настоящее SMS не отправляется: код приходит в `debug_code` и пишется в лог сервиса.

1. Откройте `http://localhost:8001/docs`.
2. В каждом запросе нажмите Try it out, вставьте JSON из шагов 1–3 и нажмите Execute.
3. Скопируйте `access_token` из ответа регистрации, нажмите Authorize справа вверху и вставьте его.
4. Вызовите `GET /api/v1/users/me` — должен вернуться профиль.

Частые ошибки:

- `JSON decode error` — в Request body попало что-то кроме JSON: лишние кавычки `""eyJ...""` или целая команда `curl`. В поле должен быть только JSON от `{` до `}`.
- В Authorize вставляется сам токен, без слова `Bearer`.
- Код из SMS и `verification_token` живут недолго (5 и 10 минут). Если на тест ушло больше времени, начните с шага 1.
