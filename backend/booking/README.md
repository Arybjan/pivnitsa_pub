# 🍺 Pivnitsa Pub

Краткое описание проекта.

## 🚀 Технологии

- Python
- FastAPI
- PostgreSQL
- Docker
- Redis

---

## 📥 Клонирование проекта

```bash
git clone https://github.com/Arybjan/pivnitsa_pub.git
cd pivnitsa_pub
```

---

## ⚙️ Установка

### Создание виртуального окружения

```bash
python -m venv .venv
```

Windows

```bash
.venv\Scripts\activate
```

Linux/macOS

```bash
source .venv/bin/activate
```

Установка зависимостей

```bash
pip install -r requirements.txt
```

---

## 🔐 Настройка окружения

Создать файл

```
.env
```

Пример

```env
DEBUG=True

SECRET_KEY=

DB_NAME=
DB_USER=
DB_PASSWORD=
DB_HOST=
DB_PORT=

REDIS_HOST=
REDIS_PORT=
```

---

## 🗄 Миграции

```bash
alembic upgrade head
```

---

## ▶ Запуск проекта

```bash
uvicorn app.main:app --reload
```

---

## 🐳 Запуск через Docker

```bash
docker compose up --build
```

Остановка

```bash
docker compose down
```

---

## 📁 Структура проекта

```
backend/
frontend/
docker/
nginx/
app/
...
```

---

## 🌿 Git Flow

Создать ветку

```bash
git checkout -b feature/login
```

Перед отправкой

```bash
git pull origin develop
git push origin feature/login
```

Создать Pull Request.

---

## 📝 Правила разработки

- Не коммитить `.env`
- Перед коммитом запускать тесты
- Использовать Black
- Использовать Ruff/Flake8
- Именование веток:
  - feature/*
  - fix/*
  - hotfix/*
  - refactor/*

---

## 🤝 Участие в разработке

1. Создать ветку
2. Сделать изменения
3. Проверить код
4. Commit
5. Push
6. Pull Request

## API броней: комментарий, номер стола, авторизация

### Комментарий к брони

`POST /api/v1/bookings` принимает необязательное поле `comment`, не длиннее 500 символов.
Пробелы по краям обрезаются. Пустая строка и строка из пробелов сохраняются как `null`.
Если строка длиннее 500 символов, ответ будет `422`. Комментарий хранится в
`bookings.comment` (миграция `e7b3c9d1f4a6`) и возвращается во всех ответах с бронью.

```json
{"table_id": 5, "event_id": 3, "guests": 2, "comment": "У окна, будет торт"}
```

### Номер стола

В каждом ответе с бронью рядом с `table_id` есть `table_number`. Booking не хранит номер:
он берётся из Venue Service одним запросом `GET /api/v1/tables/numbers` на весь ответ
(для списка тоже один запрос, без N+1). Адрес Venue задаётся в `VENUE_SERVICE_URL`.
Если переменная пустая, Venue недоступен или стол не найден, `table_number` будет `null`.
Бронь при этом всё равно отдаётся, а `table_id` остаётся прежним.

```json
{"id": 1, "user_id": 42, "table_id": 5, "table_number": 15, "comment": null, "...": "..."}
```

### Авторизация

Все эндпоинты требуют `Authorization: Bearer <access_token>` от Auth Service. Пользователь
определяется только по `sub` проверенного токена, `user_id` из запроса не используется.
Без заголовка, с неверной подписью, с просроченным токеном, с `type` не `access`
(refresh, service) или с нечисловым `sub` ответ `401`. При `is_active=false` ответ `403`.
Чужую бронь пользователь не видит (`403`) и не может отменить (`404`).

## Тесты

```bash
pip install -r requirements-dev.txt
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5440/booking_test pytest -q
```

Тесты пересоздают указанную БД и применяют все миграции.
