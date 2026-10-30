import { useEffect, useState } from "react";
import { sendOtp, verifyOtp } from "../../api/auth";


interface CodeStepProps {
  phone: string;
  purpose: 'login' | 'register';
  onBack: () => void;
  onVerifySuccess: (token: string) => void;
}


export function CodeStep({ phone, purpose, onBack, onVerifySuccess }: CodeStepProps) {
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [countdown, setCountdown] = useState(60);

  const canResend = countdown <= 0;
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


  // Таймер обратного отсчета
  useEffect(() => {
    if(countdown <= 0) return;
    const timer = setTimeout(() => setCountdown((c) => c - 1), 1000);

    return () => clearTimeout(timer);
  }, [countdown]);


  // стандарт: форма SubmitEvent<HTMLFormElement>; кнопка MouseEvent<HTMLButtonElement>; инпут ChangeEvent<HTMLInputElement>
  const handleSubmit = async (e: React.SubmitEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError('');

    if(code.length < 4) return setError('Введите код из SMS');

    setIsLoading(true);
    try {
      const data = await verifyOtp(`+996${phone}`, code, purpose);
      onVerifySuccess(data.verification_token); // передаем токен
    } catch(err: unknown) {
      const message = err instanceof Error ? err.message : 'Неверный код';
      setError(translateError(message));
    } finally {
      setIsLoading(false);
    }
  };


  const handleResend = async () => {
    setError('');

    try {
      const data = await sendOtp(`+996${phone}`, purpose);
      // показываем код в консоли (режим разработки)
      if(data.debug_code) {
        console.log('%c[SMS CODE]: ' + data.debug_code, 'color: #fec200; font-size: 16px; font-weight: bold;');
        alert(`Тестовый режим! Ваш код: ${data.debug_code}`);
      }
      setCountdown(60);
    } catch(err: unknown) {
      const message = err instanceof Error ? err.message : 'Не удалось повторно отправить код.'
      setError(translateError(message));
      console.error(err);
    }
  };


  const formattedPhone = `+996 ${phone.slice(0, 3)} ${phone.slice(3, 6)} ${phone.slice(6, 9)}`;

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <p className="text-tg-hint text-sm">
        Код отправлен на <span className="text-tg-text font-medium">{formattedPhone}</span>
      </p>

      <div>
        <label className="block text-tg-hint text-sm mb-2">
          Код из SMS
        </label>

        <input
          type="text"
          inputMode="numeric"
          autoComplete="one-time-code" // ios и android сами предложат код из SMS
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          placeholder="123456"
          className="w-full rounded-xl bg-white/5 border border-white/10 px-4 py-3 text-tg-text text-center text-2xl tracking-widest
                    outline-none focus:border-brand/50 transition-colors"
        />
        {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
      </div>

      <div className="flex items-center justify-between text-xs">
        <button
          type="button"
          onClick={onBack}
          className="text-tg-hint hover:text-tg-text transition-colors"
        >
          &larr; Изменить номер
        </button>

        {canResend ? (
          <button
            type="button"
            onClick={handleResend}
            className="text-brand hover:text-brand-hover transition-colors font-semibold"
          >
            Отправить снова
          </button>
        ) : (
          <span className="text-tg-hint">
            Отправить через {countdown} с
          </span>
        )}
      </div>

      <button
        type="submit"
        disabled={isLoading}
        className="btn btn-fancy w-full py-3 text-base font-bold disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isLoading ? 'Проверка...' : 'Войти'}
      </button>
    </form>
  );
}