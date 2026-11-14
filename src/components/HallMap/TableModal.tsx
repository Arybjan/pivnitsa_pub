import { useEffect, useState } from "react";
import type { Event, MapTable } from "../../types/api";
import { CONFIG } from "../../lib/config";
import { bishkekToISO, formatDateShort, formatTime } from "../../lib/date";


interface TableModalProps {
  table: MapTable | null;
  date: string;
  // мероприятие на выбранную дату - тогда время берется из него
  event: Event | null;
  onClose: () => void;
  onBook: (guests: number, comment: string, time: string) => Promise<void>;
  isBooking: boolean;
  bookingError: string | null;
}


// для единобразия строк label - value
function Row({ label, children, accent = false }: { label: string; children: React.ReactNode; accent?: boolean; }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-tg-hint">{label}</span>
      <span className={accent ? 'text-brand font-bold text-base' : 'text-tg-text font-semibold'}>{children}</span>
    </div>
  );
};


export function TableModal({ table, date, event, onClose, onBook, isBooking, bookingError }: TableModalProps) {
  const [guests, setGuests] = useState<number>(() => {
    // если capacity нет, считаем, что = 2
    // ?? - оператор нулевого слияния - "если слева undefined / null, то берем то, что справа"
    const cap = table?.capacity ?? 2;
    
    return cap >= 2 ? 2 : 1;
  });

  const [comment, setComment] = useState('');

  // если есть ивент на этот день - ставим время ивента, иначе стандартное
  const [time, setTime] = useState<string>(() => event ? formatTime(event.starts_at) : CONFIG.DEFAULT_BOOKING_TIME);
  const [timeError, setTimeError] = useState('');


  useEffect(() => {
    if(!table) return;

    const handler = (e: KeyboardEvent) => {
      if(e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);

    return () => window.removeEventListener('keydown', handler);
  }, [table, onClose]);


  // отключение скролла страницы при активной модалке
  useEffect(() => {
    if(!table) return;

    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.body.style.overflow = prev; // очистка эффекта при закрытии модалки или !table (восстановление сохраненного значения)
    };
  }, [table]);


  if(!table) return null;

  const handleSubmit = (e: React.SubmitEvent<HTMLFormElement>) => {
    e.preventDefault();
    setTimeError('');

    if(guests > table.capacity) return;
    if(!time) return setTimeError('Укажите время');

    const [h, m] = time.split(':').map(Number);
    const mins = h * 60 + m;

    // рабочее время бара - 1140 минут до 23:59 или 300 минут от 00:00 до 05:00
    const isValid = mins >= CONFIG.OPEN_HOUR * 60 || mins <= CONFIG.CLOSE_HOUR * 60;
    if(!isValid) return setTimeError(`Бар работает с ${CONFIG.OPEN_HOUR}:00 до 0${CONFIG.CLOSE_HOUR}:00`);

    // проверяем, что выбранное время еще не прошло (при сегодняшней брони)
    const selectedDateTime = bishkekToISO(date, time);
    if(new Date(selectedDateTime).getTime() <= Date.now()) return setTimeError('Нельзя забронировать столик в прошлом!');

    onBook(guests, comment, time);
  };


  const dateLabel = formatDateShort(date);

  const displayPrice = table.price ?? CONFIG.DEFAULT_TABLE_PRICE;


  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 backdrop-blur-sm animate-fade-in"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-md bg-tg-secondary rounded-t-3xl p-6 animate-slide-up"
        onClick={(e) => e.stopPropagation()}
      >

        {/* стиль выдвижной панели */}
        <div className="w-12 h-1 rounded-full bg-white/15 mx-auto mb-5 sm:hidden" />

        {/* заголовок + крестик */}
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-tg-text">
            Бронирование
          </h2>

          <button
            type="button"
            onClick={onClose}
            aria-label="Закрыть"
            className="w-9 h-9 flex items-center justify-center rounded-full bg-white/5 text-tg-hint hover:bg-white/10 hover:text-tg-text transition-colors"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* список полей */}
        <div className="space-y-3 mb-6 bg-white/5 p-4 rounded-xl">
          {event ? (
            <>
              <Row label='Мероприятие'>{event.title}</Row>
              <Row label='Дата и время'>{dateLabel}, {formatTime(event.starts_at)}</Row>
            </>
          ) : (
            <Row label='Дата'>{dateLabel}</Row>
          )}
          <Row label='Столик'>№{table.number} (мест: {table.capacity})</Row>
          <Row label='К оплате' accent>
            {/* table.price вместо displayPrice */}
            {displayPrice.toLocaleString('ru')} сом
          </Row>
        </div>


        <form onSubmit={handleSubmit} className="space-y-4">
          {/* время выбирается только для брони без мероприятия */}
          <div>
            <label htmlFor="booking-time" className="block text-tg-hint text-sm mb-2">
              Время
            </label>
            <input
              id="booking-time"
              type="time"
              value={time}
              onChange={(e) => setTime(e.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-tg-text outline-none focus:border-brand/50 transition-colors"
            />
            {timeError && <p className="text-red-400 text-xs mt-2">{timeError}</p>}

            {event && (
              <p className="text-brand text-xs mt-2">
                ⚡ В это время проходит: {event.title}
              </p>
            )}
          </div>

          <div>
            <label className="block text-tg-hint text-sm mb-2">Количество гостей</label>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setGuests(g => Math.max(1, g - 1))}
                className="w-10 h-10 rounded-lg bg-white/5 hover:bg-white/10 flex items-center justify-center text-xl font-bold"
              >
                -
              </button>

              <input
                type="number"
                value={guests}
                onChange={(e) => setGuests(Number(e.target.value))}
                min={1}
                max={table.capacity}
                className="w-16 text-center bg-transparent text-xl font-bold outline-none"
              />

              <button
                type="button"
                onClick={() => setGuests(g => Math.min(table.capacity, g + 1))}
                className="w-10 h-10 rounded-lg bg-white/5 hover:bg-white/10 flex items-center justify-center text-xl font-bold"
              >
                +
              </button>
              <span className="text-tg-hint text-xs ml-auto">макс. {table.capacity}</span>
            </div>

            {guests > table.capacity && (
            <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl space-y-2 mt-2">
              <p className="text-amber-400 text-xs mt-1">
                Гостей больше, чем мест за столиком. Убедитесь, что столики будут сдвинуты.
              </p>
              <a
                href="https://wa.me/996706606606"
                target="_blank"
                rel="noopener noreferrer"
                className="text-amber-400 text-xs font-semibold underline hover:text-amber-300"
              >
                Свяжитесь с нами.
              </a>
            </div>
            )}
          </div>

          <div>
            <label className="block text-tg-hint text-sm mb-2">Дополнительная информация (необязательно)</label>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Например: хотим сесть у окна, нужна романтическая атмосфера..."
              rows={2}
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-tg-text outline-none focus:border-brand/50 transition-colors resize-none"
            />
          </div>

          {bookingError && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {bookingError}
            </div>
          )}

          <button
            type="submit"
            disabled={isBooking}
            className="btn btn-fancy btn-fancy-pulse w-full py-4 text-base font-bold disabled:opacity-50"
          >
            {isBooking ? 'Оформление...' : 'Забронировать и оплатить'}
          </button>
        </form>

      </div>
    </div>
  );
}