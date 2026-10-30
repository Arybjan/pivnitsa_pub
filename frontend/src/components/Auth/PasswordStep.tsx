import { useState } from "react";
import { registerUser } from "../../api/auth";
import { useAuth } from "../../context/useAuth";


interface PasswordStepProps {
  verificationToken: string;
  phone: string;
  onSuccess: () => void;
}


export function PasswordStep({ verificationToken, phone, onSuccess }: PasswordStepProps) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const { login } = useAuth();
  
  const translateError = (msg: string): string => {
    const map: Record<string, string> = {
      'Invalid code': 'Неверный код',
      'Code expired or not requested': 'Код истёк. Запросите новый.',
      'Too many invalid attempts, request a new code': 'Слишком много попыток. Запросите новый код.',
      'Phone number is already registered': 'Этот номер уже зарегистрирован. Войдите.',
      'Code was sent recently, try again later': 'Код уже отправлен. Подождите немного.',
      'Too many codes requested, try again later': 'Слишком много запросов. Попробуйте позже.',
      'Invalid or expired verification token': 'Сессия истекла. Начните заново.',
      'Password must contain at least one letter and one digit': 'Пароль должен содержать буквы и цифры',
    };
    // если нет в словаре, показываем как есть
    return map[msg] || msg;
  };


  const handleSubmit = async (e: React.SubmitEvent<HTMLFormElement>) => {
    e.preventDefault();
    if(password.length < 8) return setError('Пароль должен состоять минимум из восьми символов.');

    // регулярное выражение: минимум 8 символов, хотя бы 1 буква и 1 цифра
    const passwordRegex = /^(?=.*[A-Za-z])(?=.*\d).{8,}$/;
    if(!passwordRegex.test(password)) return setError('Пароль должен состоять минимум из восьми символов, содержать хотя бы одну цифру и одну заглавную букву.');

    setIsLoading(true);
    try {
      // создаем аккаунт и получаем токены
      const data = await registerUser(verificationToken, password);
      // сохраняем токен и юзера в контекст (login сохранит токен в storage)
      await login(data.access_token, data.refresh_token, data.user);

      onSuccess();
    } catch(err: unknown) {
      const message = err instanceof Error ? err.message : 'Ошибка регистрации.';
      setError(translateError(message));
    } finally {
      setIsLoading(false);
    }
  };


  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <p className="text-tg-hint text-sm">Придумайте пароль для входа с номера +996{phone}</p>

      <div>
        <label className="block text-tg-hint text-sm mb-2">Пароль</label>

        <div className="relative">
          <input
            type={showPassword ? 'text' : 'password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Минимум 8 символов"
            className="w-full rounded-xl bg-white/5 border border-white/10 px-4 py-3 text-tg-text outline-none focus:border-brand/50"
          />

          {/* глаз отображения пароля */}
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-tg-hint hover:text-white transition-colors"
          >
            {showPassword ? (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                <circle cx="12" cy="12" r="3"/>
              </svg>
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
                <line x1="1" y1="1" x2="23" y2="23"/>
              </svg>
            )}
          </button>
        </div>
        
        {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
      </div>

      <button type="submit" disabled={isLoading} className="btn btn-fancy w-full py-3 text-base font-bold">
        {isLoading ? 'Регистрация...' : 'Завершить'}
      </button>
    </form>
  );
}