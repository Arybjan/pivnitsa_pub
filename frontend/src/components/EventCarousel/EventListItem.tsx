import type { Event } from "../../types/api";
import { formatEventDateShort, truncate } from "../../lib/date";


interface EventListItemProps {
  event: Event;
  onOpen: (event: Event) => void;
}


const FALLBACK_POSTER = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(
  `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">
    <rect width="100%" height="100%" fill="#121212"/>
    <text x="50%" y="50%" fill="#a1a1aa" font-family="system-ui, sans-serif" font-size="22" font-weight="500" text-anchor="middle" dominant-baseline="middle">Нет афиши</text>
  </svg>`
)}`;


export function EventListItem({ event, onOpen }: EventListItemProps) {
  return (
    <button
      type="button"
      onClick={() => onOpen(event)}
      className="group w-full flex gap-4 p-3 rounded-2xl bg-tg-secondary border border-white/5 hover:border-brand/40 transition-colors text-left"
    >

      {/* картинка слева */}
      <div className="relative w-28 h-28 sm:w-36 sm:h-36 shrink-0 rounded-xl overflow-hidden bg-black/50">
        <img
          src={event.poster_url || FALLBACK_POSTER}
          alt={event.title}
          draggable={false}
          className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
          onError={(e) => {
            e.currentTarget.onerror = null;
            e.currentTarget.src = FALLBACK_POSTER;
          }}
        />
      </div>

      {/* текст справа */}
      <div className="flex flex-col flex-1 py-1 justify-between min-w-0">
        <div>
          <span className="text-brand text-xs font-semibold block mb-1">
            {formatEventDateShort(event.starts_at)}
          </span>

          <h3 className="text-tg-text font-bold text-base leading-tight line-clamp-2 mb-2">
            {event.title}
          </h3>

          <p className="text-tg-hint text-xs leading-snug line-clamp-2">
            {truncate(event.description || 'Описание отсутствует.', 90)}
          </p>
        </div>
      </div>

    </button>
  );
}