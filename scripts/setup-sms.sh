#!/usr/bin/env bash
# Включение настоящих SMS через Nikita (smspro.nikita.kg).
# Спрашивает логин, пароль API (ввод скрыт) и имя отправителя, пишет их в .env
# и перезапускает auth и notification. Пароль никуда, кроме .env, не выводится.
#
#   ./scripts/setup-sms.sh          - тестовый режим Nikita (SMS не уходят, деньги не списываются)
#   ./scripts/setup-sms.sh --live   - боевой режим (настоящие SMS)
#   ./scripts/setup-sms.sh --off    - выключить, код снова в логе и на странице
set -euo pipefail

cd "$(dirname "$0")/.."
ENV_FILE=.env
[ -f "$ENV_FILE" ] || cp .env.example "$ENV_FILE"

# key=value в .env: заменить строку или дописать
set_env() {
  local key="$1" value="$2"
  python3 - "$ENV_FILE" "$key" "$value" <<'PY'
import sys
path, key, value = sys.argv[1:4]
lines = open(path).read().splitlines()
for i, line in enumerate(lines):
    if line.startswith(key + "="):
        lines[i] = f"{key}={value}"
        break
else:
    lines.append(f"{key}={value}")
open(path, "w").write("\n".join(lines) + "\n")
PY
}

restart() {
  docker compose up -d auth notification >/dev/null 2>&1
  echo "Сервисы перезапущены."
}

if [ "${1:-}" = "--off" ]; then
  set_env SMS_PROVIDER console
  set_env OTP_EXPOSE_IN_RESPONSE true
  restart
  echo "SMS выключены: код снова в логе auth и на странице входа."
  exit 0
fi

if [ "${1:-}" = "--live" ]; then
  current_login=$(grep -E '^NIKITA_LOGIN=' "$ENV_FILE" | cut -d= -f2- || true)
  if [ -n "$current_login" ]; then
    set_env NIKITA_TEST_MODE false
    restart
    echo "Боевой режим: SMS уходят на телефоны (платно)."
    exit 0
  fi
fi

echo "Данные из личного кабинета smspro.nikita.kg"
read -r -p "Логин (тот же, что для входа в кабинет): " login
read -r -s -p "Пароль API/SMPP (ввод не отображается): " password; echo
read -r -p "Имя отправителя (из раздела отправителей): " sender

[ -n "$login" ] && [ -n "$password" ] && [ -n "$sender" ] || { echo "Нужно заполнить все три поля."; exit 1; }

set_env SMS_PROVIDER notification
set_env OTP_EXPOSE_IN_RESPONSE false
set_env NIKITA_LOGIN "$login"
set_env NIKITA_PASSWORD "$password"
set_env NIKITA_SENDER "$sender"
set_env NIKITA_TEST_MODE "$([ "${1:-}" = "--live" ] && echo false || echo true)"
chmod 600 "$ENV_FILE"

restart
if [ "${1:-}" = "--live" ]; then
  echo "Готово, боевой режим: SMS уходят на телефоны."
else
  echo "Готово, тестовый режим: Nikita проверяет данные, но SMS не отправляет."
  echo "Напишите в чат «готово» - проверю ответ шлюза."
fi
