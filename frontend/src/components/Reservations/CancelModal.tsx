import { useState } from "react";
import type { BookingResponse } from "../../types/api";
import { formatDateShort } from "../../lib/date";


interface CancelModalProps {
  reservation: BookingResponse | null;
  onClose: () => void;
  onConfirm: (reason: string) => void;
}


export function CancelModal({reservation, onClose, onConfirm}: CancelModalProps) {
  const [reason, setReason] = useState('');

  if(!reservation) return null;

  const handleSubmit = (e: React.SubmitEvent<HTMLFormElement>) => {
    e.preventDefault();
    onConfirm(reason.trim() || 'Без указания причины');
  };


  // форматируем дату (booking_date при наличии, иначе вырезаем дату из starts_at)
  const dateStr = reservation.booking_date || reservation.starts_at?.split('T')[0] || '';
  const displayDate = dateStr ? formatDateShort(dateStr) : 'неизвестно';
  const displayTime = reservation.starts_at ? new Date(reservation.starts_at).toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' }) : '';


  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-md bg-tg-secondary rounded-2xl p-6 animate-zoom-in"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-xl font-bold text-tg-text mb-2">Отменить бронь?</h2>

        <p className="text-tg-hint text-sm mb-4">
          Бронь на стол №{reservation.table_id} ({displayDate} в {displayTime && `в ${displayTime}`}) будет отменена.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-tg-hint text-xs mb-2">
              Причина отмены (необязательно)
            </label>

            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Например: изменились планы"
              rows={3}
              className="w-full rounded-xl bg-white/5 border border-white/10 px-3 py-2 text-tg-text text-sm outline-none
                      focus:border-brand/50 transition-colors resize-none"
            />
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="btn btn-secondary flex-1 py-3 text-sm font-semibold"
            >
              Ещё подумаю
            </button>

            <button
              type="submit"
              className="btn btn-outline-danger flex-1 py-3 text-sm font-bold"
            >
              Отменить
            </button>
          </div>
        </form>

      </div>
    </div>
  );
}