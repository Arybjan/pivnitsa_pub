#!/usr/bin/env bash
# Первый запуск стенда «Пивница» на любом компьютере.
#
#   git clone -b infra/local-stack https://github.com/Arybjan/pivnitsa_pub.git pivnitsa-infra
#   cd pivnitsa-infra
#   ./scripts/bootstrap.sh
#
# Что делает:
#   1. проверяет git и Docker
#   2. скачивает ветки сервисов и админки в ./src (git worktree)
#   3. создаёт .env со случайным JWT_SECRET
#   4. собирает и запускает стенд, ждёт готовности сервисов
#   5. по желанию регистрирует ваш номер и делает его владельцем
#
# Повторный запуск обновляет ветки до свежих и перезапускает стенд, .env и данные не трогает.
#   --no-owner   не спрашивать номер владельца
#   OWNER_PHONE=+996... OWNER_PASSWORD=... ./scripts/bootstrap.sh   - без вопросов
set -euo pipefail

# Ветки сервисов. После слияния PR в командные ветки замените на них
# (или переопределите при запуске: AUTH_BRANCH=auth-service ./scripts/bootstrap.sh)
AUTH_BRANCH="${AUTH_BRANCH:-fix/auth-cors-retry-after}"
EVENT_BRANCH="${EVENT_BRANCH:-fix/event-int-user-id}"
VENUE_BRANCH="${VENUE_BRANCH:-feat/venue-table-occupied}"
BOOKING_BRANCH="${BOOKING_BRANCH:-fix/booking-app-event-date}"
PAYMENT_BRANCH="${PAYMENT_BRANCH:-payment-service}"
NOTIFICATION_BRANCH="${NOTIFICATION_BRANCH:-fix/notification-sms-delivery-result}"
ADMIN_BRANCH="${ADMIN_BRANCH:-feature/fe-admin-backend}"

ASK_OWNER=1
[ "${1:-}" = "--no-owner" ] && ASK_OWNER=0

cd "$(dirname "$0")/.."
ROOT="$(pwd)"

say()  { printf '\n\033[1;33m==> %s\033[0m\n' "$*"; }
fail() { printf '\n\033[1;31mОшибка: %s\033[0m\n' "$*" >&2; exit 1; }


# 1. Инструменты
say "Проверяю git и Docker"
command -v git >/dev/null || fail "не найден git: https://git-scm.com/downloads"
command -v docker >/dev/null || fail "не найден Docker: установите Docker Desktop https://www.docker.com/products/docker-desktop/"
docker compose version >/dev/null 2>&1 || fail "нужен Docker Compose v2 (входит в Docker Desktop)"
docker info >/dev/null 2>&1 || fail "Docker не запущен - откройте Docker Desktop и повторите"
command -v curl >/dev/null || fail "не найден curl"
git rev-parse --git-dir >/dev/null 2>&1 || fail "запускайте из клона репозитория (git clone -b infra/local-stack ...)"


# 2. Ветки сервисов в ./src
say "Скачиваю сервисы и админку"
mkdir -p src

checkout() {
  local name="$1" branch="$2"
  git fetch -q origin "+refs/heads/$branch:refs/remotes/origin/$branch" \
    || fail "ветка $branch не найдена на GitHub"

  if [ -d "src/$name" ]; then
    # уже скачан: переходим на свежий коммит, если там нет незакоммиченных правок
    if [ -n "$(git -C "src/$name" status --porcelain)" ]; then
      echo "  $name: есть локальные правки - оставляю как есть"
      return
    fi
    git -C "src/$name" checkout -q --detach "origin/$branch"
  else
    git worktree add -q --detach "src/$name" "origin/$branch"
  fi
  echo "  $name <- $branch ($(git -C "src/$name" log -1 --format=%h))"
}

checkout auth "$AUTH_BRANCH"
checkout event "$EVENT_BRANCH"
checkout venue "$VENUE_BRANCH"
checkout booking "$BOOKING_BRANCH"
checkout payment "$PAYMENT_BRANCH"
checkout notification "$NOTIFICATION_BRANCH"
checkout admin "$ADMIN_BRANCH"


# 3. .env (только при первом запуске)
if [ ! -f .env ]; then
  say "Создаю .env"
  cp .env.example .env
  secret="$(python3 -c 'import secrets; print(secrets.token_hex(32))' 2>/dev/null || openssl rand -hex 32)"
  python3 - "$secret" <<'PY' 2>/dev/null || fail "нужен python3 для настройки .env"
import sys
values = {
    "JWT_SECRET": sys.argv[1],
    "AUTH_DIR": "./src/auth",
    "EVENT_DIR": "./src/event",
    "VENUE_DIR": "./src/venue/services/venue-service",
    "BOOKING_DIR": "./src/booking",
    "PAYMENT_DIR": "./src/payment",
    "NOTIFICATION_DIR": "./src/notification",
    "ADMIN_FRONTEND_DIR": "./src/admin",
}
lines = open(".env").read().splitlines()
for i, line in enumerate(lines):
    key = line.split("=", 1)[0]
    if key in values and not line.startswith("#"):
        lines[i] = f"{key}={values[key]}"
open(".env", "w").write("\n".join(lines) + "\n")
PY
  chmod 600 .env
else
  echo "  .env уже есть - не меняю"
fi


# Порты стенда свободны? (запущенный этот же стенд не мешает)
busy=""
for port in 3000 8001 8002 8003 8004 8005 8006 5440 6390 5672 15672; do
  if (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then busy="$busy $port"; fi
done
if [ -n "$busy" ] && [ -z "$(docker compose ps -q 2>/dev/null)" ]; then
  fail "заняты порты:$busy - остановите то, что их использует, и повторите"
fi


# 4. Сборка и запуск
say "Собираю и запускаю стенд (первый раз - несколько минут)"
docker compose up -d --build

say "Жду готовности сервисов"
for port in 8001 8002 8003 8004 8005 8006 3000; do
  printf '  :%s ' "$port"
  for _ in $(seq 1 90); do
    code="$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:$port/" || true)"
    [ "$code" != "000" ] && break
    sleep 2
  done
  [ "$code" != "000" ] && echo "ok" || fail "сервис на порту $port не поднялся: docker compose logs"
done


# 5. Владелец
api() { curl -s -X POST "http://localhost:8001/api/v1$1" -H 'Content-Type: application/json' -d "$2"; }
json() { python3 -c "import sys, json; d = json.load(sys.stdin); print($1)"; }

make_owner() {
  local phone="$1"
  if docker compose exec -T auth python -m app.cli set-role "$phone" owner 2>/dev/null; then
    return
  fi

  # номера ещё нет - регистрируем (код в dev-режиме приходит в ответе)
  local password="${OWNER_PASSWORD:-}" password2
  if [ -z "$password" ]; then
    read -r -s -p "  Придумайте пароль (от 8 символов, буквы и цифры): " password; echo
    read -r -s -p "  Повторите пароль: " password2; echo
    [ "$password" = "$password2" ] || { echo "  Пароли не совпали - пропускаю"; return; }
  fi

  local code token result
  code="$(api /auth/otp/send "{\"phone\":\"$phone\",\"purpose\":\"register\"}" | json "d.get('debug_code') or ''")"
  [ -n "$code" ] || { echo "  Не удалось получить код (включены настоящие SMS?) - зарегистрируйтесь на странице регистрации"; return; }
  token="$(api /auth/otp/verify "{\"phone\":\"$phone\",\"code\":\"$code\",\"purpose\":\"register\"}" | json "d.get('verification_token', '')")"
  result="$(PASSWORD="$password" python3 -c 'import json, os, sys; print(json.dumps({"verification_token": sys.argv[1], "password": os.environ["PASSWORD"]}))' "$token" \
    | curl -s -X POST http://localhost:8001/api/v1/auth/register -H 'Content-Type: application/json' -d @- | json "d.get('user', {}).get('phone') or d.get('detail')")"
  echo "  Регистрация: $result"
  docker compose exec -T auth python -m app.cli set-role "$phone" owner || true
}

if [ -n "${OWNER_PHONE:-}" ]; then
  say "Владелец админ-панели"
  make_owner "$OWNER_PHONE"
elif [ "$ASK_OWNER" = 1 ] && [ -t 0 ]; then
  say "Владелец админ-панели"
  read -r -p "  Ваш номер (+996XXXXXXXXX, Enter - пропустить): " phone
  [ -n "$phone" ] && make_owner "$phone"
fi


say "Готово"
cat <<EOF
  Админка:   http://localhost:3000/login-form/index.html
  Сервисы:   auth :8001  booking :8002  venue :8003  payment :8004  notification :8005  event :8006
  Код входа: виден на странице входа и в логах (docker compose logs auth)

  Остановить:  docker compose stop
  Обновить:    ./scripts/bootstrap.sh --no-owner
  Владелец:    docker compose exec auth python -m app.cli set-role +996XXXXXXXXX owner
EOF
