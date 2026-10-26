import { Link, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { useAuth } from "../context/useAuth";
import { AuthSheet } from "../components/Auth/AuthSheet";
import { authStorage } from "../lib/auth-storage";
import { updateMe } from "../api/auth";


export function ProfilePage() {
  const { user, updateUser } = useAuth();
  const navigate = useNavigate();

  const [isAuthOpen, setIsAuthOpen] = useState(true);
  const [firstName, setFirstName] = useState(user?.first_name ?? '');
  const [lastName, setLastName] = useState(user?.last_name ?? '');
  const [email, setEmail] = useState(user?.email ?? '');
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');


  useEffect(() => {
    if(user) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setFirstName(user.first_name ?? '');
      setLastName(user.last_name ?? '');
      setEmail(user.email ?? '');
    }
  }, [user]);


  // если авторизации нет, а модалку закрыли - редирект на главную
  const handleAuthClose = () => {
    setIsAuthOpen(false);
    navigate('/');
  };


  // если гость не авторизован
  if(!user) {
    return (
      <div className="min-h-screen bg-tg-bg flex items-center justify-center">
        {isAuthOpen && (
          <AuthSheet
            onClose={handleAuthClose}
            onSuccess={() => setIsAuthOpen(false)}
          />
        )}
      </div>
    );
  }


  const handleSave = async (e: React.SubmitEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError('');

    // простая валидация email
    if(email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return setError('Введите корректный e-mail');

    setIsSaving(true);
    try {
      const token = await authStorage.getToken();
      if(!token) throw new Error('Нет токена авторизации');

      const updatedUser = await updateMe({
        first_name: firstName,
        last_name: lastName,
        email
      }, token);
      
      // обновляем глобальный контекст, чтобы имя сразу поменялось везде
      updateUser(updatedUser);
      alert('Профиль успешно сохранён!');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Ошибка сохранения';
      setError(message);
    } finally {
      setIsSaving(false);
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
          <h1 className="text-2xl font-bold tracking-tight">Настройки профиля</h1>
        </header>

        <section className="px-5 pb-10">
          <form onSubmit={handleSave} className="card p-6 flex flex-col gap-5">

            {/* телефон - только для чтения */}
            <div>
              <label className="block text-tg-hint text-sm mb-2">Телефон</label>
              <div className="w-full rounded-xl bg-white/5 border border-white/10 px-4 py-3 text-tg-hint text-base">
                {user.phone}
              </div>

              <p className="text-xs text-tg-hint mt-1">Номер изменить нельзя</p>
            </div>

            {/* имя */}
            <div>
              <label htmlFor="firstName" className="block text-tg-hint text-sm mb-2">Имя</label>
              <input
                id="firstName"
                type="text"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                className="w-full rounded-xl bg-white/5 border border-white/10 px-4 py-3 text-tg-text text-base outline-none focus:border-brand/50 transition-colors"
                placeholder="Иван"
              />
            </div>

            {/* фамилия */}
            <div>
              <label htmlFor="lastName" className="block text-tg-hint text-sm mb-2">Фамилия</label>
              <input
                id="lastName"
                type="text"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                className="w-full rounded-xl bg-white/5 border border-white/10 px-4 py-3 text-tg-text text-base outline-none focus:border-brand/50 transition-colors"
                placeholder="Иванов"
              />
            </div>

            {/* Email */}
            <div>
              <label htmlFor="email" className="block text-tg-hint text-sm mb-2">E-mail</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-xl bg-white/5 border border-white/10 px-4 py-3 text-tg-text text-base outline-none focus:border-brand/50 transition-colors"
                placeholder="your@example.com"
              />

              {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
            </div>

            <div className="flex gap-3 mt-2">
              <button
                type="submit"
                disabled={isSaving}
                className="btn btn-primary flex-1 py-3 text-base font-bold disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSaving ? 'Сохранение...' : 'Сохранить'}
              </button>
            </div>

          </form>
        </section>

      </div>
    </div>
  );
}