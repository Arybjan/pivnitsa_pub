import { useEffect, useRef, useState } from "react";
import { useNotifications } from "../../hooks/useNotification";
import { formatDateShort } from "../../lib/date";
import { markNotificationAsRead } from "../../api/notification";
import { authStorage } from "../../lib/auth-storage";
import { useQueryClient } from "@tanstack/react-query";


export function NotificationsDropdown() {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const { data: notifications, isLoading } = useNotifications();


  // закрытие при клике вне меню
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if(dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) setIsOpen(false);
    };

    if(isOpen) document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);


  // есть ли непрочитанные
  const hasUnread = notifications?.some((n) => !n.is_read);


  const queryClient = useQueryClient();

  useEffect(() => {
    // если меню открыто и есть непрочитанные
    if(!isOpen || !notifications) return;

    const markAll = async () => {
      const unread = notifications.filter(n => !n.is_read);
      if(unread.length === 0) return;

      const token = await authStorage.getToken();
      if(!token) return;

      // отмечаем все непрочитанные как прочитанные
      await Promise.all(unread.map(n => markNotificationAsRead(n.id, token).catch(() => {})));

      // обновляем кэш, чтобы точка пропала
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    };

    markAll();
  }, [isOpen, notifications, queryClient]);


  return (
    <div className="relative" ref={dropdownRef}>
      {/* иконка колокольчика */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Уведомления"
        className="relative w-9 h-9 flex items-center justify-center rounded-full bg-white/5 hover:bg-white/10 border border-white/10 transition-colors"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>

        {/* индикатор непрочитанных */}
        {hasUnread && (
          <span className="absolute top-2 right-2.5 w-2 h-2 bg-red-500 rounded-full border border-tg-bg" />
        )}
      </button>


      {/* выпадающее меню */}
      {isOpen && (
        <div className="absolute right-0 top-full mt-3 w-80 max-w-[calc(100vw-32px)] z-50">
          <div className="absolute -top-2 right-3.5 w-4 h-4 bg-tg-secondary border-t border-l border-white/10 transform rotate-45 z-10" />

          <div className="relative bg-tg-secondary border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-96">
            <div className="px-4 py-3 border-b border-white/5 bg-tg-secondary z-10">
              <h3 className="font-bold text-sm">Уведомления</h3>
            </div>

            <div className="overflow-y-auto flex-1">
              {isLoading ? (
                <div className="p-4 text-center text-tg-hint text-xs">
                  Разбираем ваши письма...
                </div>
              ) : !notifications || notifications.length === 0 ? (
                <div className="p-6 text-center text-tg-hint text-xs">
                  Нет новых уведомлений
                </div>
              ) : (
                notifications.map((notif) => (
                  <div
                    key={notif.id}
                    className={`p-4 border-b border-white/5 last:border-0 flex flex-col gap-1 transition-colors hover:bg-white/5 ${notif.is_read ? 'opacity-60' : ''}`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="font-semibold text-sm">{notif.title}</span>
                      <span className="text-[10px] text-tg-hint whitespace-nowrap mt-0.5">
                        {formatDateShort(notif.created_at)}
                      </span>
                    </div>

                    <p className="text-tg-hint text-xs leading-snug">{notif.message}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}