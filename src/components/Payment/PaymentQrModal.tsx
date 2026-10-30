import { useEffect } from "react";
import type { BookingResponse } from "../../types/api";
import { CONFIG } from "../../lib/config";
import { formatTime } from "../../lib/date";


interface PaymentQrModalProps {
  booking: BookingResponse | null;
  onClose: () => void;
}


// +996706606606 -> +996 706 606 606
function formatPhone(digits: string): string {
  return `+${digits.slice(0, 3)} ${digits.slice(3, 6)} ${digits.slice(6, 9)} ${digits.slice(9)}`;
}


export function PaymentQrModal({ booking, onClose }: PaymentQrModalProps) {
  useEffect(() => {
    if(!booking) return;

    const handler = (e: KeyboardEvent) => {
      if(e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);

    return () => window.removeEventListener('keydown', handler);
  }, [booking, onClose]);


  if(!booking) return null;

  const tableLabel = booking.table_number ?? booking.table_id;

  // готовое сообщение, чтобы админ сразу нашел бронь
  const whatsappText = `Здравствуйте! Отправляю чек об оплате брони №${booking.id} (стол №${tableLabel}).`;
  const whatsappUrl = `https://wa.me/${CONFIG.PAYMENT_WHATSAPP}?text=${encodeURIComponent(whatsappText)}`;


  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-sm bg-tg-secondary rounded-2xl p-6 animate-zoom-in text-center"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-xl font-bold text-tg-text mb-1">Оплата брони</h2>
        <p className="text-tg-hint text-sm mb-5">Бронь №{booking.id} · стол №{tableLabel}</p>

        <img
          src={CONFIG.PAYMENT_QR_URL}
          alt="QR-код для оплаты"
          className="w-56 h-56 mx-auto rounded-xl bg-white p-2 object-contain"
        />

        {booking.total_amount && (
          <p className="text-brand font-bold text-lg mt-4">
            {Number(booking.total_amount).toLocaleString('ru')} сом
          </p>
        )}

        <p className="text-tg-text text-sm mt-4">
          Отсканируйте QR в приложении банка и отправьте чек на WhatsApp{' '}
          <span className="font-semibold whitespace-nowrap">{formatPhone(CONFIG.PAYMENT_WHATSAPP)}</span>
        </p>

        {booking.status === 'PENDING_PAYMENT' && (
          <p className="text-amber-400 text-xs mt-2">
            Бронь держится до {formatTime(booking.expires_at)}. После проверки чека администратор подтвердит её.
          </p>
        )}

        <div className="flex flex-col gap-2 mt-6">
          <a
            href={whatsappUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-primary w-full py-3 text-sm font-bold"
          >
            Отправить чек в WhatsApp
          </a>

          <button
            type="button"
            onClick={onClose}
            className="btn btn-secondary w-full py-3 text-sm font-semibold"
          >
            Готово
          </button>
        </div>
      </div>
    </div>
  );
}
