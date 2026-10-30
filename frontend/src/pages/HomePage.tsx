import { useCallback, useState } from "react";
import { EventCarousel } from "../components/EventCarousel/EventCarousel";
import { useBarOpenStatus } from "../hooks/useBarOpenStatus";
import { HallMap } from "../components/HallMap/HallMap";
import type { MapTable } from "../types/api";
import { TableModal } from "../components/HallMap/TableModal";
import { DatePicker } from "../components/HallMap/DatePicker";
import { todayISO } from "../lib/date";
import { Link } from "react-router-dom";
import { AuthSheet } from "../components/Auth/AuthSheet";
import { authStorage } from "../lib/auth-storage";
import { useRequireAuth } from "../hooks/useRequireAuth";
import { useHalls, useHallMap } from "../hooks/useHallMap";
import { createBooking } from "../api/booking";
import { createPayment } from "../api/payment";
import { NewbieGuideline } from "../components/Tutorial/NewbieGuideline";
import { NotificationsDropdown } from "../components/Layout/NotificationsDropdown";
import { ProfileDropdown } from "../components/Layout/ProfileDropdown";
import { Preloader } from "../components/Layout/Preloader";
import { usePublishedEvents } from "../hooks/useEvents";


export function HomePage() {
  const isOpen = useBarOpenStatus();

  const [userSelectedHallId, setUserSelectedHallId] = useState<number | undefined>(undefined);
  const [selectedDate, setSelectedDate] = useState<string>(todayISO());
  const [selectedTable, setSelectedTable] = useState<MapTable | null>(null);
  const [isAuthOpen, setIsAuthOpen] = useState(false);
  const [isBooking, setIsBooking] = useState(false);
  const [bookingError, setBookingError] = useState<string | null>(null);

  const openAuth = useCallback(() => setIsAuthOpen(true), []);
  const closeAuth = useCallback(() => setIsAuthOpen(false), []);
  const requireAuth = useRequireAuth({ onNeedAuth: openAuth }); 


  // получаем список залов с backend
  const { data: halls, isLoading: isHallsLoading, isError: isHallsError } = useHalls();

  // выбираем первый зал при рендере (если ничего не выбрано юзером)
  const selectedHallId = userSelectedHallId ?? halls?.[0]?.id;

  // получаем карту зала
  const { data: hallMap } = useHallMap(selectedHallId);

  // достаем ивенты
  const { data: eventsData } = usePublishedEvents();
  const events = eventsData?.items ?? [];
  const firstEventId = events.length > 0 ? events[0].id : 1; // id первого ивента или undefined при их отсутствии

  // проверка, грузится ли что-то
  const isInitialLoading = isHallsLoading || (selectedHallId && !hallMap);


  const handleBook = async (guests: number, comment: string) => {
    if(!selectedTable) return;

    setIsBooking(true);
    setBookingError(null);

    try {
      const token = await authStorage.getToken();
      if(!token) throw new Error('Вы не авторизованы');

      // создаем бронь
      const booking = await createBooking({
        table_id: selectedTable.id,
        event_id: firstEventId,
        guests,
        comment: comment || undefined,
      }, token);

      // создаем платеж на основе этой брони
      const payment = await createPayment({ booking_id: booking.id }, token);

      // открываем ссылку на оплату (при ее наличии)
      if(payment.checkout_url) {
        // в TG открываем через системный браузер
        const tg = window.Telegram?.WebApp;
        if(tg?.openLink) tg.openLink(payment.checkout_url);
        // fallback для браузера
        else window.open(payment.checkout_url);

        // закрываем модалку бронирования
        setSelectedTable(null);
      } else throw new Error('Не удалось получить ссылку на оплату');
    } catch(err: unknown) {
      const message = err instanceof Error ? err.message : 'Не удалось создать бронь';
      setBookingError(message);
    } finally {
      setIsBooking(false);
    }
  };

  
  return (
    <div className="min-h-screen bg-tg-bg text-tg-text flex flex-col relative">
      {(isInitialLoading) && <Preloader />}
      <NewbieGuideline />
      <div className="w-full max-w-3xl mx-auto flex-1 flex flex-col">

        <header className="px-5 pt-5 pb-6 flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">🍺 Пивница</h1>
            <p className="text-tg-hint text-sm mt-1">Ночной бар - Бишкек</p>
          </div>

          <div className="flex items-center gap-2">
            <span id="tour-worktime" className={isOpen ?
              'text-[11px] font-semibold uppercase tracking-wider ' +
              'text-green-400 bg-green-500/10 border border-green-500/20 ' +
              'px-2.5 py-1 rounded-full'
            :
              'text-[11px] font-semibold uppercase tracking-wider ' +
              'text-tg-hint bg-white/5 border border-white/10 ' +
              'px-2.5 py-1 rounded-full'
            }>
              {isOpen ? 'Открыто' : 'Закрыто'}
            </span>

            <NotificationsDropdown />

            <ProfileDropdown />
          </div>
        </header>

        <section id="tour-events" className="px-5">
          <div className="flex items-baseline justify-between mb-3">
            <h2 className="text-lg font-bold">Афиша</h2>
            <Link
              to={'/events'}
              id="tour-events-all"
              className="text-brand hover:text-brand-hover transition-colors text-xs font-semibold"
            >
              Все мероприятия &rarr;
            </Link>
          </div>

          <EventCarousel />
        </section>

        <section id="tour-map" className="px-5 mt-8">
          <h2 className="text-lg font-bold mb-3">Карта зала</h2>

          <div className="flex items-center justify-between mb-4 gap-3">
            <DatePicker value={selectedDate} onChange={setSelectedDate} />
            
            {/* переключатель залов */}
            {halls && halls.length > 0 &&(
              <div className="flex gap-1 p-1 rounded-xl bg-tg-secondary border border-white/5">
                {halls.map((hall) => (
                  <button
                    key={hall.id}
                    type="button"
                    onClick={() => setUserSelectedHallId(hall.id)}
                    className={"px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors " +
                      (selectedHallId === hall.id ? 'bg-brand text-black' : 'text-tg-hint hover:text-tg-text')
                    }
                  >
                    {hall.name}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* обработка загрузки и ошибок */}
          {isHallsLoading ? (
            <div className="h-64 md:h-80 bg-tg-secondary animate-pulse rounded-2xl flex items-center justify-center text-tg-hint text-sm">
              Устанавливаем столики...
            </div>
          ) : isHallsError ? (
            <div className="h-64 md:h-80 flex flex-col items-center justify-center bg-tg-secondary rounded-2xl text-tg-hint text-sm text-center px-4">
              <p className="text-red-400 mb-2">Сервер временно недоступен</p>
              <p>Не удалось загрузить схему зала.</p>
              <p>Проверьте подключение к интернету или попробуйте позже.</p>
            </div>
          ) : hallMap ? (
            <HallMap
              tables={hallMap.tables}
              selectedTableId={selectedTable?.id}
              onSelectTable={(table) => requireAuth(() => setSelectedTable(table))}
            />
          ) : null}
        </section>

        <section className="px-5 mt-8 flex flex-col gap-3">
          {/* <button
            type="button"
            onClick={() => {
              document.getElementById('hall-map-section')?.scrollIntoView({ behavior: "smooth" });
            }}
            className="btn btn-fancy btn-fancy-pulse w-full md:w-auto md:px-10 py-4 text-base font-bold"
          >
            Забронировать столик
          </button> */}

          <Link
            to={'/my'}
            id="tour-mybookings"
            className="btn btn-secondary w-full md:w-auto md:px-10 py-4 text-sm font-semibold text-center"
          >
            Мои активные брони
          </Link>
        </section>

        <footer className="mt-auto px-5 pt-8 pb-5 text-tg-hint text-xs space-y-1 flex items-center flex-col">
          <p>Работаем ежедневно с 19:00 по 05:00</p>
          <p>г. Бишкек, ул. Сухэ-Батора, 3/4</p>

          <div className="flex gap-3">
            <a
              href="https://www.instagram.com/pivnica.kg/"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 pt-3 text-tg-hint hover:text-brand transition-colors text-sm"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
                <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
                <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
              </svg>
              @pivnica.kg
            </a>
  
            <a
              href="https://wa.me/996706606606"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 pt-3 text-tg-hint hover:text-brand transition-colors text-sm"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
              </svg>
              Связаться с нами (WhatsApp)
            </a>
          </div>
        </footer>

        {/* модалка столика (главное, что любая модалка внутри React-дерева) */}
        <TableModal
          table={selectedTable}
          date={selectedDate}
          onClose={() => setSelectedTable(null)}
          onBook={handleBook}
          isBooking={isBooking}
          bookingError={bookingError}
        />

        {/* тестовая регистрация */}
        {isAuthOpen && (
          <AuthSheet
            onClose={closeAuth}
            onSuccess={() => {
              closeAuth();
              // пока что просто закрываем
            }}
          />
        )}

      </div>
    </div>
  );
}