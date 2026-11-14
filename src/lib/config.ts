// Временные значения, заменяются на моменте, когда решатся вопросы по US
export const CONFIG = {
  MAX_BOOKING_DAYS: 14, // глубина бронирования (дни) US-14
  DEFAULT_BOOKING_TIME: '22:00', // время начало брони по умолчанию US-16
  DEFAULT_TABLE_PRICE: 30000, // цена столика по умолчанию (сом) US-16
  HALL_VIEWBOX: { width: 900, height: 550 }, // система координат карты зала (админ-панель canvas dashboard.html)
  // оплата брони переводом по QR бара, чек - в WhatsApp (QR пока заглушка)
  PAYMENT_QR_URL: '/payment-qr.svg',
  PAYMENT_WHATSAPP: '996706606606',
  
  // часы работы бара
  OPEN_HOUR: 19,
  CLOSE_HOUR: 5,
} as const;