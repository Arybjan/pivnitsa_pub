import { useEffect, useRef, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../../context/useAuth";


export function ProfileDropdown() {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const { user, logout } = useAuth();
  const navigate = useNavigate();


  // закрытие при клике вне меню
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) setIsOpen(false);
    };

    if (isOpen) document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);


  const handleLogout = async () => {
    setIsOpen(false);
    await logout();

    navigate('/');
  };


  // если не авторизован - перекидывает на вход
  if(!user) {
    return (
      <Link
        to={'/profile'}
        aria-label="Войти"
        className="w-9 h-9 flex items-center justify-center rounded-full bg-white/5 hover:bg-white/10 border border-white/10 transition-colors"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="8" r="4" />
          <path d="M4 20c0-4 3-6 8-6s8 2 8 6" />
        </svg>
      </Link>
    );
  }


  return (
    <div className="relative" ref={dropdownRef}>
      {/* иконка профиля */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Профиль"
        className="w-9 h-9 flex items-center justify-center rounded-full bg-white/5 hover:bg-white/10 border border-white/10 transition-colors"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="8" r="4" />
          <path d="M4 20c0-4 3-6 8-6s8 2 8 6" />
        </svg>
      </button>

      {/* выпадающее меню */}
      {isOpen && (
        <div className="absolute right-0 top-full mt-3 w-64 max-w-[calc(100vw-32px)] z-50">
          <div className="absolute -top-2 right-3.5 w-4 h-4 bg-tg-secondary border-t border-l border-white/10 transform rotate-45 z-10" />
          
          <div className="relative bg-tg-secondary border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col">
            {/* Шапка с именем */}
            <div className="p-4 border-b border-white/5 bg-white/5 relative z-10">
              <p className="font-bold text-sm truncate">
                {user.first_name || user.phone}
              </p>
              <p className="text-xs text-tg-hint truncate mt-0.5">{user.phone}</p>
            </div>

            {/* Кнопки меню */}
            <div className="flex flex-col p-1">
              <Link
                to="/profile"
                onClick={() => setIsOpen(false)}
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-white/5 transition-colors text-sm"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
                Настройки профиля
              </Link>

              <Link
                to="/my"
                onClick={() => setIsOpen(false)}
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-white/5 transition-colors text-sm"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                  <line x1="16" y1="2" x2="16" y2="6" />
                  <line x1="8" y1="2" x2="8" y2="6" />
                  <line x1="3" y1="10" x2="21" y2="10" />
                </svg>
                Мои брони
              </Link>

              <div className="h-px bg-white/5 my-1" />

              <button
                onClick={handleLogout}
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-red-500/10 text-red-400 transition-colors text-sm w-full text-left"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                  <polyline points="16 17 21 12 16 7" />
                  <line x1="21" y1="12" x2="9" y2="12" />
                </svg>
                Выйти
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}