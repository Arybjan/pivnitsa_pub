<!-- ЗАПУСК ДОКЕРА -->
1. Запустить Docker Desktop
2. Выйти из папки с Front-проектом на уровень ниже
3. Git Bash:
  git clone -b infra/local-stack https://github.com/Arybjan/pivnitsa_pub.git pivnitsa-infra
  cd pivnitsa-infra
4. Без этого .env выдаст ошибку по Python3. Вставить одной командой:
  secret="$(openssl rand -hex 32)" && sed -i \
  -e "s|^JWT_SECRET=.*|JWT_SECRET=$secret|" \
  -e "s|^AUTH_DIR=.*|AUTH_DIR=./src/auth|" \
  -e "s|^EVENT_DIR=.*|EVENT_DIR=./src/event|" \
  -e "s|^VENUE_DIR=.*|VENUE_DIR=./src/venue/services/venue-service|" \
  -e "s|^BOOKING_DIR=.*|BOOKING_DIR=./src/booking|" \
  -e "s|^PAYMENT_DIR=.*|PAYMENT_DIR=./src/payment|" \
  -e "s|^NOTIFICATION_DIR=.*|NOTIFICATION_DIR=./src/notification|" \
  -e "s|^ADMIN_FRONTEND_DIR=.*|ADMIN_FRONTEND_DIR=./src/admin|" .env
4. Запустить скрипт, дождаться загрузки:
  ./scripts/bootstrap.sh --no-owner
5. Роль owner выдается по номеру телефона:
  docker compose exec auth python -m app.cli set-role +996XXXXXXXXX owner
6. Остановка локального сервера (после этого можно закрывать Docker Desktop):
  docker compose stop
  ```[cite: 1]
7. Запуск сервера заново в том же состоянии, в котором он был до остановки:
  ```bash
  docker compose up -d
  ```[cite: 1]
8. Пока запущены контейнеры, всё будет работать по адресу:
  localhost:3000
9. Проверка, что всё выключено (список контейнеров должен иметь статус Exited или терминал напишет,
что запущенных контейнеров нет):
  docker compose ps



<!-- ТЕСТОВАЯ РЕГИСТРАЦИЯ -->
1. Перейти:
  http://localhost:8001/docs
2. Найти:
  POST /api/v1/auth/otp/send
3. Try it out и ввести:
  { "phone": "0705072003", "purpose": "register" }
4. Execute, в ответе скопировать:
  debug_code (типа 519966)
5. Найти:
  POST /api/v1/auth/otp/verify
6. Try it out и ввести:
  { "phone": "0705072003", "code": "519966", "purpose": "register" }
7. Execute, в ответе скопировать:
  verification_token (очень много символов)
8. Найти:
  POST /api/v1/auth/register
9. Try it out и ввести:
  { "verification_token": "...", "password": "Test1234", "first_name": "Тест", ... }
10. Execute, в ответе скопировать:
  "access_token": "..."
11. Зарегистрированный пользователь в том же ответе:
  "user": {
    "id": 3,
    "phone": "+996705072003",
    "email": "testtestovich@gmail.com",
    "role": "user",
    "is_active": true,
    "first_name": "Тест",
    "last_name": "Тестович",
    "avatar_url": null,
    "created_at": "2026-10-19T22:54:14.309957Z"
  }
12. Ввести access_token в Authorize (замок справа сверху сваггера). Каждый токен действителен короткое время