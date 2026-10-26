import { Link } from "react-router-dom";


export function EmptyReservations() {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
      <div className="w-20 h-20 mb-6 rounded-full bg-tg-secondary border border-white/5 flex items-center justify-center text-brand">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
          <line x1="16" y1="2" x2="16" y2="6" />
          <line x1="8" y1="2" x2="8" y2="6" />
          <line x1="3" y1="10" x2="21" y2="10" />
          <path d="M8 14h.01" />
          <path d="M12 14h.01" />
          <path d="M16 14h.01" />
          <path d="M8 18h.01" />
          <path d="M12 18h.01" />
          <path d="M16 18h.01" />
        </svg>
      </div>

      <h3 className="text-tg-text font-bold text-lg mb-2">
        У вас пока нет активных броней
      </h3>
      <p className="text-tg-hint text-sm mb-8 max-w-xs">
        Выберите столик на карте зала, чтобы забронировать место на вечер.
      </p>

      <Link
        to={'/'}
        className="btn btn-fancy btn-fancy-pulse px-8 py-3 text-base font-bold"
      >
        Выбрать столик
      </Link>
    </div>
  );
}