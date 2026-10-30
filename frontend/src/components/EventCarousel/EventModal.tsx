import { useEffect } from "react";
import type { Event } from "../../types/api";
import { formatEventDateLong } from "../../lib/date";
import { AuthSheet } from '../Auth/AuthSheet';
import { useState } from 'react';
import { useAuth } from '../../context/useAuth';


interface EventModalProps {
  event: Event | null;
  onClose: () => void;
}


const FALLBACK_POSTER = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(
  `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">
    <rect width="100%" height="100%" fill="#121212"/>
    <text x="50%" y="50%" fill="#a1a1aa" font-family="system-ui, sans-serif" font-size="22" font-weight="500" text-anchor="middle" dominant-baseline="middle">Нет афиши</text>
  </svg>`
)}`;


export function EventModal({ event, onClose }: EventModalProps) {
  const { isAuthenticated } = useAuth();
  const [isAuthOpen, setIsAuthOpen] = useState(false);


  const handleLike = () => {
    if(!isAuthenticated) {
      setIsAuthOpen(true);

      return;
    }

    console.log('like intent for event', event?.id)
  };


  // закрытие на esc
  useEffect(() => {
    if(!event) return;

    const handler = (e: KeyboardEvent) => {
      if(e.key === 'Escape') onClose();
    };

    window.addEventListener('keydown', handler);

    return () => window.removeEventListener('keydown', handler);
  }, [event, onClose]);


  // блок скролла body при активной модалке
  useEffect(() => {
    if(!event) return;

    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.body.style.overflow = prev;
    };
  }, [event]);


  if(!event) return null;
  const poster = event.poster_url?.trim() || FALLBACK_POSTER;


  const handleShare = () => {
    const botUsername = import.meta.env.VITE_BOT_USERNAME || 'pivnitsa_bot';
    // глубокая ссылка на бота с параметром
    // при бэкенде бот может открыть WebApp сразу на этом ивенте по /start event_XXX)
    const eventUrl = `https://t.me/${botUsername}?start=event_${event.id}`;
    const text = `${event.title} - ${formatEventDateLong(event.starts_at)}`;
    // encodeURIComponent защищает от поломки URL из-за спецсимволов
    const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(eventUrl)}&text=${encodeURIComponent(text)}`;
  
    // TG WebApp API доступен через window.Telegram.WebApp (для этого функционала был создан telegram.d.ts)
    const tg = window.Telegram?.WebApp;

    if(tg?.openTelegramLink) tg.openTelegramLink(shareUrl); // правильный способ открыть t.me внутри TG, а не во внешнем браузере (при window.open TG откроет браузер и потеряет контекст)
    else if(tg?.openLink) tg.openLink(shareUrl); // fallback откроет во внешнем окне
    else window.open(shareUrl, '_blank'); // если не в TG, а в браузере
  };


  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in duration-200"
      // клик по фону - закрывает модалку
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-2xl max-h-[90vh] overflow-hidden rounded-2xl bg-tg-secondary flex flex-col animate-zoom-in duration-200"
        // клик по карточке - не закрывает модалку
        onClick={(e) => e.stopPropagation()}
      >
        {/* крестик */}
        <button
          type="button"
          onClick={onClose}
          aria-label="Закрыть"
          className="absolute top-3 right-3 z-10 w-9 h-9 flex items-center justify-center rounded-full bg-black/60 backdrop-blur-sm text-white hover:bg-black/80 transition-colors"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <line x1='18' y1='6' x2='6' y2='18' />
            <line x1='6' y1='6' x2='18' y2='18' />
          </svg>
        </button>

        {/* картинка сверху - полная */}
        <div className="w-full shrink-0 bg-black flex items-center justify-center">
          <img
            src={poster}
            alt={event.title}
            draggable={false}
            className="w-full max-h-[50vh] object-contain"
            onError={(e) => {
              e.currentTarget.onerror = null;
              e.currentTarget.src = FALLBACK_POSTER;
            }}
          />
        </div>

        {/* текст снизу картинки */}
        <div className="flex flex-col gap-3 p-6 overflow-y-auto">
          <span className="text-brand text-sm font-semibold">
            {formatEventDateLong(event.starts_at)}
          </span>

          <h2 className="text-white text-2xl font-bold leading-tight">
            {event.title}
          </h2>

          <p className="text-white/70 text-base leading-relaxed whitespace-pre-line">
            {event.description}
          </p>

          <div className="flex flex-wrap gap-3 mt-2">
            <button
              type="button"
              className="btn btn-fancy btn-fancy-pulse mt-2 self-start px-8 py-3 text-base font-bold tracking-wide"
              onClick={handleLike}
            >
              Ждите меня!
            </button>

            <button
              type="button"
              onClick={handleShare}
              className="btn btn-secondary mt-2 px-8 py-3 text-base font-semibold inline-flex items-center gap-2"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="18" cy="5" r="3" />
                <circle cx="6" cy="12" r="3" />
                <circle cx="18" cy="19" r="3" />
                <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
                <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
              </svg>
              Пойдём со мной!
            </button>
          </div>
        </div>

        {/* защита кнопки "Ждите меня!" через авторизацию */}
        {isAuthOpen && (
          <AuthSheet
            onClose={() => setIsAuthOpen(false)}
            onSuccess={() => setIsAuthOpen(false)}
          />
        )}
      </div>
    </div>
  );
}