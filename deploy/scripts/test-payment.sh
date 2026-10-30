#!/usr/bin/env bash
# Проверка оплаты на стенде без мобильного приложения: скрипт ведёт себя как гость.
#   1. входит тестовым гостем
#   2. бронирует стол на ближайшее опубликованное мероприятие
#   3. создаёт платёж и печатает ссылку на страницу оплаты
#
#   ./scripts/test-payment.sh [гостей]           (по умолчанию 2)
#   GUEST_PHONE=+996... GUEST_PASSWORD=... ./scripts/test-payment.sh
set -euo pipefail

GUESTS="${1:-2}"
PHONE="${GUEST_PHONE:-+996555000002}"
PASSWORD="${GUEST_PASSWORD:-Guest12345!}"

AUTH=http://localhost:8001/api/v1
BOOKING=http://localhost:8002/api/v1
VENUE=http://localhost:8003/api/v1
PAYMENT=http://localhost:8004
EVENT=http://localhost:8006/api/v1

json() { python3 -c "import sys, json; d = json.load(sys.stdin); print($1)"; }
fail() { echo "Ошибка: $*" >&2; exit 1; }

# 1. Гость
LOGIN=$(curl -s -X POST "$AUTH/auth/login" -H 'Content-Type: application/json' \
  -d "{\"phone\":\"$PHONE\",\"password\":\"$PASSWORD\"}")
TOKEN=$(echo "$LOGIN" | json "d.get('access_token', '')")
if [ -z "$TOKEN" ]; then
  OTP_RESP=$(curl -s -X POST "$AUTH/auth/otp/send" -H 'Content-Type: application/json' -d "{\"phone\":\"$PHONE\"}")
  OTP_CODE=$(echo "$OTP_RESP" | json "d.get('debug_code', '')")
  if [ -n "$OTP_CODE" ]; then
    V_RESP=$(curl -s -X POST "$AUTH/auth/otp/verify" -H 'Content-Type: application/json' -d "{\"phone\":\"$PHONE\",\"code\":\"$OTP_CODE\"}")
    V_TOKEN=$(echo "$V_RESP" | json "d.get('verification_token', '')")
    if [ -n "$V_TOKEN" ]; then
      REG_RESP=$(curl -s -X POST "$AUTH/auth/register" -H 'Content-Type: application/json' \
        -d "{\"verification_token\":\"$V_TOKEN\",\"password\":\"$PASSWORD\",\"first_name\":\"Тест\",\"last_name\":\"Гость\"}")
      TOKEN=$(echo "$REG_RESP" | json "d.get('access_token', '')")
    fi
  fi
fi
[ -n "$TOKEN" ] || fail "гость $PHONE не вошёл: $LOGIN"
AUTH_HEADER="Authorization: Bearer $TOKEN"

# 2. Ближайшее опубликованное мероприятие
EVENT_JSON=$(curl -s "$EVENT/events?limit=1")
EVENT_ID=$(echo "$EVENT_JSON" | json "d['items'][0]['id'] if d['items'] else ''")
[ -n "$EVENT_ID" ] || fail "нет опубликованных будущих мероприятий - опубликуйте одно в админке"
EVENT_TITLE=$(echo "$EVENT_JSON" | json "d['items'][0]['title']")

# свободный стол: пробуем по очереди, занятые бэкенд отклонит
BOOKING_ID=""
for TABLE_ID in $(curl -s "$VENUE/tables" | json "' '.join(str(t['id']) for t in d if t['status'] == 'ACTIVE')"); do
  RESPONSE=$(curl -s -X POST "$BOOKING/bookings" -H "$AUTH_HEADER" -H 'Content-Type: application/json' \
    -d "{\"table_id\":$TABLE_ID,\"event_id\":$EVENT_ID,\"guests\":$GUESTS}")
  BOOKING_ID=$(echo "$RESPONSE" | json "d.get('id', '')")
  [ -n "$BOOKING_ID" ] && break
done
[ -n "$BOOKING_ID" ] || fail "все столы на «${EVENT_TITLE}» заняты"

# 3. Платёж
PAYMENT_JSON=$(curl -s -X POST "$PAYMENT/api/v1/payments" -H "$AUTH_HEADER" -H 'Content-Type: application/json' \
  -d "{\"booking_id\":$BOOKING_ID}")
CHECKOUT=$(echo "$PAYMENT_JSON" | json "d.get('checkout_url', '')")
AMOUNT=$(echo "$PAYMENT_JSON" | json "d.get('amount', '')")
[ -n "$CHECKOUT" ] || fail "платёж не создан: $PAYMENT_JSON"

cat <<EOF

Бронь #$BOOKING_ID: стол id $TABLE_ID на «${EVENT_TITLE}», гостей: $GUESTS
Сумма к оплате: $AMOUNT сом. Бронь держится 15 минут.

Откройте страницу оплаты по QR-коду и подтвердите оплату («Я оплатил(а) депозит»):
  $PAYMENT$CHECKOUT

Потом в админке: «Схема зала» -> «Список броней» на дату мероприятия.
Бронь станет «Активна», оплата «Оплачено». Если отменить бронь там — депозит вернётся по правилам заведения (100% за сутки, 50% менее 24ч).
EOF
