import { Link } from "react-router-dom";
import { useAuth } from "../context/useAuth";
import type { BookingResponse } from "../types/api";
import { useState } from "react";
import { CancelModal } from "../components/Reservations/CancelModal";
import { EmptyReservations } from "../components/Reservations/EmptyReservations";
import { useMyBookings } from "../hooks/useMyBookings";
import { useQueryClient } from "@tanstack/react-query";
import { cancelBooking } from "../api/booking";
import { authStorage } from "../lib/auth-storage";
import { formatDateShort } from "../lib/date";
import { createPayment } from "../api/payment";
import { API } from "../api/client";


export function MyReservationsPage() {
  const { isAuthenticated } = useAuth();
  const queryClient = useQueryClient();
  const { data: bookings, isLoading, isError } = useMyBookings();

  // стейт для модалки отмены
  const [bookingToCancel, setBookingToCancel] = useState<BookingResponse | null>(null);
  // стейт для возобновления платежа
  const [payingId, setPayingId] = useState<number | null>(null);


  // если не авторизован - просим войти
  if(!isAuthenticated) {
    return (
      <div className="min-h-screen bg-tg-bg text-tg-text flex flex-col items-center justify-center p-5">
        <p className="text-tg-hint mb-4">Войдите, чтобы увидеть свои брони</p>
        <Link to={'/'} className="btn btn-primary px-6 py-3">На главную</Link>
      </div>
    );
  }


  // фильтруем и сортируем (ближайшая бронь - первая)
  const activeBookings = (bookings || [])
        .filter((b) => b.status === 'CONFIRMED' || b.status === 'PENDING_PAYMENT')
        .sort((a, b) => {
          const dateA = a.starts_at || a.booking_date || '';
          const dateB = b.starts_at || b.booking_date || '';

          return dateA.localeCompare(dateB);
        });

  
  const handleCancelConfirm = async (reason: string) => {
    if(!bookingToCancel) return;

    try {
      const token = await authStorage.getToken();
      if(!token) throw new Error('Нет токена');

      await cancelBooking(bookingToCancel.id, reason, token);

      // обновляем кэш React Query, чтобы список перерисовался без перезагрузки страницы
      queryClient.invalidateQueries({ queryKey: ['myBookings'] });
      setBookingToCancel(null);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Не удалось отменить бронь';
      alert(message);
    }
  }


  const handlePay = async (booking: BookingResponse) => {
    setPayingId(booking.id);
    try {
      const token = await authStorage.getToken();
      if(!token) throw new Error('Вы не авторизованы');

      // создаем платеж для уже существующей брони
      const payment = await createPayment({ booking_id: booking.id }, token);

      if(payment.checkout_url) {
        // при относительной ссылке с /, добавляем домен бэкенда
        const fullUrl = payment.checkout_url.startsWith('http') ?
              payment.checkout_url : `${API.payment}${payment.checkout_url}`;

        const tg = window.Telegram?.WebApp;

        if(tg?.openLink) tg.openLink(fullUrl);
        else window.open(fullUrl, '_blank');
      } else throw new Error('Не удалось получить ссылку на оплату');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Ошибка при переходе к оплате';
      alert(message);
    } finally {
      setPayingId(null);
    }
  };


  return (
    <div className="min-h-screen bg-tg-bg text-tg-text flex flex-col">
      <div className="w-full max-w-3xl mx-auto flex-1 flex flex-col">

        <header className="px-5 pt-8 pb-5">
          <Link
            to={'/'}
            className="inline-flex items-center gap-1 text-tg-hint hover:text-brand transition-colors text-sm mb-4"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            Назад
          </Link>

          <h1 className="text-2xl font-bold tracking-tight">Мои брони</h1>
        </header>

        <section className="px-5 pb-10 flex flex-col gap-3">
          {isLoading ? (
            <div className="h-40 bg-tg-secondary animate-pulse rounded-2xl flex items-center justify-center text-tg-hint text-sm">
              Загрузка броней...
            </div>
          ) : isError ? (
            <div className="h-40 flex items-center justify-center bg-tg-secondary text-red-400 rounded-2xl text-sm">
              Не удалось загрузить брони :/
            </div>
          ) : activeBookings.length === 0 ? (
            <EmptyReservations />
          ) : (
            activeBookings.map((res, index) => (
              <div
                key={res.id}
                className="animate-fade-in-up"
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <ReservationCard
                  res={res}
                  onCancel={() => setBookingToCancel(res)}
                  onPay={() => handlePay(res)}
                  isPaying={payingId === res.id}
                />
              </div>
            ))
          )}
        </section>

        <CancelModal
          reservation={bookingToCancel}
          onClose={() => setBookingToCancel(null)}
          onConfirm={handleCancelConfirm}
        />
      </div>
    </div>
  );
}


function ReservationCard({ res, onCancel, onPay, isPaying }: { res: BookingResponse; onCancel: () => void; onPay: () => void; isPaying: boolean; }) {
  // форматируем дату
  const displayDate = res.booking_date ? formatDateShort(res.booking_date) : '-';
  const displayTime = res.starts_at ? new Date(res.starts_at).toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' }) : '';


  return (
    <div className="card p-5 flex flex-col gap-3">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-brand text-xs font-semibold">
            {displayDate} {displayTime && `· ${displayTime}`}
          </p>

          <h3 className="text-tg-text text-lg font-bold mt-1">
            Стол №{res.table_number ?? res.table_id}
          </h3>

          {res.comment && (
            <p className="text-xs text-tg-hint italic bg-white/5 p-2 rounded mt-1">
              '{res.comment}'
            </p>
          )}
        </div>
        
        <span
          className={res.status === 'CONFIRMED' ?
            'text-xs font-semibold text-green-400 bg-green-500/10 px-2 py-1 rounded' :
            'text-xs font-semibold text-amber-400 bg-amber-500/10 px-2 py-1 rounded'
          }
        >
          {res.status === 'CONFIRMED' ? 'Оплачено' : 'Ожидает оплаты'}
        </span>
      </div>

      <div className="flex items-center justify-between text-sm text-tg-hint">
        <span>{res.guests} гостей</span>
        <span className="text-tg-text font-semibold">
          {res.total_amount ? `${Number(res.total_amount).toLocaleString('ru')} сом` : 'Сумма уточняется'}
        </span>
      </div>

      <div className="pt-3 mt-1 border-t border-white/5 flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={onCancel}
          className="text-red-400 hover:text-red-300 text-xs font-semibold transition-colors"
        >
          Отменить бронь
        </button>

        {/* кнопка оплаты показывается только при неоплаченных */}
        {res.status === 'PENDING_PAYMENT' && (
          <button
            type="button"
            onClick={onPay}
            disabled={isPaying}
            className="btn btn-primary px-4 py-2 text-xs font-bold disabled:opacity-50"
          >
            {isPaying ? 'Переход...' : 'Оплатить'}
          </button>
        )}
      </div>
    </div>
  );
}