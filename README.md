# Pivnitsa (Пивница) — MVP

Единый монорепозиторий бара «Пивница»: клиентское веб-приложение для гостей, панель администратора и микросервисный бэкенд.

---

## Структура проекта

```
pivnitsa/
├── frontend/             # Гостевое WebApp / PWA (React 19, TypeScript, Vite, Tailwind)
├── admin/                # Панель управления баром (HTML/JS/CSS, Nginx)
├── backend/              # Микросервисы (Python 3.12, FastAPI, SQLAlchemy, Alembic)
│   ├── auth/             # Авторизация (OTP по SMS, роли, профили)
│   ├── booking/          # Бронирование столиков, холд на 15 мин, отмена
│   ├── venue/            # Схема залов, столики, статусы занятости и цены
│   ├── payment/          # Платежный шлюз, чекаут, возвраты
│   ├── notification/     # SMS-уведомления (Nikita SMS / console dev)
│   └── event/            # Афиша и мероприятия
├── deploy/               # Инфраструктурные скрипты и конфигурации баз
│   ├── postgres/         # Скрипт инициализации БД всех сервисов
│   └── scripts/          # Скрипт проверки тестовой оплаты
├── docker-compose.yml    # Запуск всех компонентов одной командой
└── .env.example          # Переменные окружения по умолчанию
```

---

## Быстрый старт

Для запуска нужен только **Docker Desktop** (версии с Docker Compose v2).

```bash
# 1. Создать локальный .env из шаблона
cp .env.example .env

# 2. Запустить весь стек
docker compose up -d --build
```

---

## Адреса сервисов

| Компонент | Адрес | Описание |
|---|---|---|
| **Гостевое WebApp** | [http://localhost:5173](http://localhost:5173) | Афиша, интерактивная карта зала, бронирование |
| **Админ-панель** | [http://localhost:3000/login-form/index.html](http://localhost:3000/login-form/index.html) | Управление бронями, залом, афишей и отчёты |
| **Auth Service** | [http://localhost:8001/docs](http://localhost:8001/docs) | Swagger API сервиса авторизации |
| **Booking Service** | [http://localhost:8002/docs](http://localhost:8002/docs) | Swagger API сервиса бронирования |
| **Venue Service** | [http://localhost:8003/docs](http://localhost:8003/docs) | Swagger API сервиса карты зала и столов |
| **Payment Service** | [http://localhost:8004/docs](http://localhost:8004/docs) | Swagger API платежного сервиса |
| **Notification Service** | [http://localhost:8005/docs](http://localhost:8005/docs) | Swagger API сервиса уведомлений |
| **Event Service** | [http://localhost:8006/docs](http://localhost:8006/docs) | Swagger API сервиса мероприятий |
| **PostgreSQL** | `localhost:5440` | Базы данных (user: `postgres`, pass: `postgres`) |
| **RabbitMQ UI** | [http://localhost:15672](http://localhost:15672) | Панель брокера сообщений (guest / guest) |
| **Redis** | `localhost:6390` | Кэш и сессии |

---

## Первый вход и создание владельца

1. Зарегистрируйтесь через Swagger сервиса Auth ([http://localhost:8001/docs](http://localhost:8001/docs)) или форму входа:
   - `POST /api/v1/auth/otp/send` → получить OTP (в dev-режиме код возвращается в поле `debug_code` и пишется в консоль).
   - `POST /api/v1/auth/otp/verify` → подтвердить номер телефона.
   - `POST /api/v1/auth/register` → завершить регистрацию паролем.
2. Назначьте роль владельца (`owner`) или администратора (`admin`):
   ```bash
   docker compose exec auth python -m app.cli set-role +996555000001 owner
   ```
3. Войдите в админ-панель под этим номером: [http://localhost:3000/login-form/index.html](http://localhost:3000/login-form/index.html).

---

## Тестирование оплаты

Скрипт имитирует процесс со стороны гостя (авторизация, выбор стола, удержание и создание ссылки на тестовую оплату):

```bash
./deploy/scripts/test-payment.sh
```

Перейдите по сгенерированной ссылке и нажмите «Оплатить тестовой картой Visa» — бронь подтвердится, а предоплата отобразится в админке.

---

## Полезные команды

```bash
# Логи конкретного сервиса (например, auth для просмотра OTP)
docker compose logs -f auth

# Пересобрать отдельный сервис после правок
docker compose up -d --build booking

# Остановить стенд
docker compose stop

# Полная очистка с удалением томов баз данных
docker compose down -v
```
