# Pivnitsa — локальный стенд

Все сервисы, PostgreSQL, Redis, RabbitMQ и админка одной командой.

## Быстрый старт (для всей команды)

Нужен только **Docker Desktop** (и git). Python, PostgreSQL и остальное - в контейнерах.

```bash
git clone -b infra/local-stack https://github.com/Arybjan/pivnitsa_pub.git pivnitsa-infra
cd pivnitsa-infra
./scripts/bootstrap.sh
```

Скрипт скачает сервисы и админку в `./src`, создаст `.env`, соберёт и запустит стенд
и предложит сделать ваш номер владельцем. Через несколько минут админка откроется на
http://localhost:3000/login-form/index.html

Обновить до свежих веток: `./scripts/bootstrap.sh --no-owner`.
Windows: запускайте из WSL или Git Bash.

Ниже - ручная раскладка, по которой стенд собирался изначально.

## Структура папок

Каждый сервис — отдельный git worktree рядом с этой папкой (пути настраиваются в `.env`):

```
pivnitsa_dev/
  infra/          ← эта ветка (infra/local-stack)
  auth/           ← auth-service
  event/          ← event_service
  venue/          ← feature/venue-service
  booking/        ← booking-service
  payment/        ← payment-service
  notification/   ← notification
pivnitsa_pub/     ← feature/fe-admin-panel (админка)
```

## Запуск

```bash
cp .env.example .env
docker compose up -d --build
```

| Что | Адрес |
|---|---|
| Админка | http://localhost:3000/login-form/index.html |
| Auth | http://localhost:8001/docs |
| Booking | http://localhost:8002/docs |
| Venue | http://localhost:8003/docs |
| Payment | http://localhost:8004/docs |
| Notification | http://localhost:8005/docs |
| Event | http://localhost:8006/docs |
| PostgreSQL | localhost:5440 (postgres/postgres, база на каждый сервис) |
| RabbitMQ UI | http://localhost:15672 (guest/guest) |

## Первый владелец / админ

OTP-код в dev возвращается в ответе `/auth/otp/send` (`debug_code`) и печатается в лог auth.

1. Зарегистрироваться (через Swagger auth: `otp/send` → `otp/verify` → `register`, purpose=register).
2. Выдать роль:
   ```bash
   docker compose exec auth python -m app.cli set-role +996555000001 owner   # или admin
   ```
3. Войти в админку по этому номеру.

## Полезное

```bash
docker compose logs -f auth            # логи сервиса (тут же OTP-коды)
docker compose up -d --build event     # пересобрать один сервис после правок
docker compose down -v                 # снести всё вместе с базами
```

## Проверка оплаты (без мобильного приложения)

```bash
./scripts/test-payment.sh 2     # тестовый гость бронирует стол на 2 человек
```

Скрипт печатает ссылку на страницу оплаты (sandbox, реальные деньги не списываются).
Нажмите «Оплатить тестовой картой Visa» - бронь станет подтверждённой, предоплата
попадёт в админку и в отчёт. Отмена этой брони в админке вернёт деньги (payment.refunded).
