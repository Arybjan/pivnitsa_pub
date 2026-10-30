// Временные значения, заменяются на моменте, когда решатся вопросы по US
export const CONFIG = {
  // глубина бронирования (дни) US-14
  MAX_BOOKING_DAYS: 14,
  // время начало брони по умолчанию US-16
  DEFAULT_BOOKING_TIME: '22:00',
  // последнее время начала брони и шаг выбора времени (мин)
  LAST_BOOKING_TIME: '23:30',
  BOOKING_TIME_STEP: 30,
  // цена столика по умолчанию (сом) US-16
  DEFAULT_TABLE_PRICE: 30000,
  // система координат карты зала (админ-панель canvas dashboard.html)
  HALL_VIEWBOX: { width: 900, height: 550 },
  // оплата брони переводом по QR бара, чек - в WhatsApp (QR пока заглушка)
  PAYMENT_QR_URL: '/payment-qr.svg',
  PAYMENT_WHATSAPP: '996706606606',
  // часы работы бара
  OPEN_HOUR: 19,
  CLOSE_HOUR: 5,
} as const;