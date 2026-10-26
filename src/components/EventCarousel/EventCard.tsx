import { formatEventDateShort } from "../../lib/date";
import type { Event } from "../../types/api";


interface EventCardProps {
  event: Event;
  onOpen: (event: Event) => void;
}


// заглушка, как data-URI в events.js админ-панели
const FALLBACK_POSTER = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(
  `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">
    <rect width="100%" height="100%" fill="#121212"/>
    <text x="50%" y="50%" fill="#a1a1aa" font-family="system-ui, sans-serif" font-size="22" font-weight="500" text-anchor="middle" dominant-baseline="middle">Нет афиши</text>
  </svg>`
)}`;



export function EventCard({ event, onOpen }: EventCardProps) {
  const poster = event.poster_url?.trim() || FALLBACK_POSTER;

  return (
    <button
      type="button"
      onClick={() => onOpen(event)}
      className="group relative w-full h-full overflow-hidden rounded-2xl bg-tg-secondary text-left"
    >
      <img
        src={poster}
        alt={event.title}
        draggable={false}
        className="absolute inset-0 w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
        onError={(e) => {
          e.currentTarget.onerror = null;
          e.currentTarget.src = FALLBACK_POSTER;
        }}
      />

      {/* градиент снизу для читаемости текста */}
      <div className="absolute inset-x-0 bottom-0 h-2/3 bg-gradient-to-t from-black/95 via-black/60 to-transparent" />
    
      {/* весь контент поверх картинки */}
      <div className="relative h-full flex flex-col justify-end p-5">

        <span className="text-brand text-xs font-semibold mb-1">
          {formatEventDateShort(event.starts_at)}
        </span>
        <h3 className="text-white text-xl font-bold leading-tight mb-2 line-clamp-2">
          {event.title}
        </h3>
        <p className="text-white/70 text-sm leading-snug line-clamp-2">
          {event.description || 'Описание отсутствует.'}
        </p>

      </div>
    </button>
  );
}