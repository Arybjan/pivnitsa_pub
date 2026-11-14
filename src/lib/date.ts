import { ru } from 'date-fns/locale'
import { formatInTimeZone, fromZonedTime } from 'date-fns-tz'
import { CONFIG } from './config';


// фикс проблемы, когда Бишкекские с 00 до 06 - это UTC+6 "вчера"
const TZ = 'Asia/Bishkek'

// для превью карусели "14 окт, 22:00"
export function formatEventDateShort(iso: string): string {
  return formatInTimeZone(new Date(iso), TZ, 'd MMM, HH:mm', { locale: ru });
}

// для подробной инфы "14 октября 2026, 22:00"
export function formatEventDateLong(iso: string): string {
  return formatInTimeZone(new Date(iso), TZ, 'd MMMM yyyy, HH:mm', { locale: ru });
}


export function isBarOpenNow(): boolean {
  // получаем время Бишкека вне зависимости от TZ юзера
  const now = new Date();
  const hourStr = formatInTimeZone(now, TZ, 'H');
  const hour = Number(hourStr);

  // с 19 до 5, переход через полночь
  return hour >= CONFIG.OPEN_HOUR || hour < CONFIG.CLOSE_HOUR;
}

// возвращает читаемое время до открытия / закрытия (пригодится для тултипа)
export function getOpenStatusLabel(): string {
  return isBarOpenNow() ? 'Открыто' : 'Закрыто';
}


// обрезка текста для превью карусели (на всякий случай)
export function truncate(text: string, max: number): string {
  if(text.length <= max) return text;

  return text.slice(0, max).trimEnd() + '...';
}


// === ФОРМАТИРОВАНИЕ ДАТ ДЛЯ КАРТЫ ЗАЛА ===
// сегодняшняя дата в TZ Бишкека - в админ-панели исправить баг с toISOString (когда 0-6 Бишкека = вчера)
export function todayISO(): string {
  return formatInTimeZone(new Date(), TZ, 'yyyy-MM-dd');
}

// за сколько дней вперед максимум можно забронировать столик
export function maxBookingDateISO(): string {
  const today = new Date();
  const max = new Date(today);

  max.setDate(today.getDate() + CONFIG.MAX_BOOKING_DAYS);

  return formatInTimeZone(max, TZ, 'yyyy-MM-dd');
}

// читаемая дата для UI: '12 июля'
export function formatDateShort(iso: string): string {
  return formatInTimeZone(new Date(iso), TZ, 'd MMMM', { locale: ru });
}


// === ВРЕМЯ БРОНИ ===
// дата мероприятия по Бишкеку: '2026-10-14'
export function dateInBishkek(iso: string): string {
  return formatInTimeZone(new Date(iso), TZ, 'yyyy-MM-dd');
}

// мероприятие еще не началось (на начавшееся бэкенд бронь не примет)
export function isUpcoming(iso: string): boolean {
  return new Date(iso).getTime() > Date.now();
}

// время мероприятия по Бишкеку: '22:00'
export function formatTime(iso: string): string {
  return formatInTimeZone(new Date(iso), TZ, 'HH:mm');
}

// дата + время по Бишкеку -> ISO с часовым поясом для бэкенда
// если после полуночи, прибавляет день к дате
export function bishkekToISO(date: string, time: string): string {
  const hour = Number(time.split(':')[0]);
  let targetDate = date;

  if(hour < CONFIG.CLOSE_HOUR) {
    const d = new Date(`${date}T12:00:00`);
    d.setDate(d.getDate() + 1);
    targetDate = formatInTimeZone(d, TZ, 'yyyy-MM-dd');
  }

  return fromZonedTime(`${targetDate}T${time}:00`, TZ).toISOString();
}