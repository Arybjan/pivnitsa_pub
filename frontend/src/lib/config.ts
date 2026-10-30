// Временные значения, заменяются на моменте, когда решатся вопросы по US
export const CONFIG = {
  // глубина бронирования (дни) US-14
  MAX_BOOKING_DAYS: 14,
  // время начало брони по умолчанию US-16
  DEFAULT_BOOKING_TIME: '22:00',
  // цена столика по умолчанию (сом) US-16
  DEFAULT_TABLE_PRICE: 30000,
  // система координат карты зала (админ-панель canvas dashboard.html)
  HALL_VIEWBOX: { width: 900, height: 550 },
  // часы работы бара
  OPEN_HOUR: 19,
  CLOSE_HOUR: 5,
} as const;