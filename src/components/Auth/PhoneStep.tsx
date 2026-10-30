import { useState } from "react";
import { sendOtp } from "../../api/auth";


interface PhoneStepProps {
  onCodeSent: (phone: string, purpose: 'login' | 'register') => void;
}


export function PhoneStep({ onCodeSent }: PhoneStepProps) {
  const [phone, setPhone] = useState('');
  const [agree, setAgree] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const translateError = (msg: string): string => {
    const map: Record<string, string> = {
      'Invalid code': 'Неверный код.',
      'Code expired or not requested': 'Код истёк. Запросите новый.',
      'Too many invalid attempts, request a new code': 'Слишком много попыток. Запросите новый код.',
      'Phone number is already registered': 'Этот номер уже зарегистрирован. Войдите.',
      'Code was sent recently, try again later': 'Код уже отправлен. Подождите немного.',
      'Too many codes requested, try again later': 'Слишком много запросов. Попробуйте позже.',
      'Invalid or expired verification token': 'Сессия истекла. Начните заново.',
      'Password must contain at least one letter and one digit': 'Пароль должен содержать буквы и цифры.',
    };
    // если нет в словаре, показываем как есть
    return map[msg] || msg;
  };


  const handleSubmit = async (e: React.SubmitEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError('');

    if(phone.length !== 9) return setError('Номер должен состоять из девяти цифр.');
    if(!agree) return setError('Пожалуйста, ознакомьтесь с нашими условиями.');

    setIsLoading(true);
    // Сначала регистрация: только она явно отвечает 409, если номер уже есть.
    // Отправка кода на вход для незнакомого номера всегда успешна (бэк не раскрывает, есть ли аккаунт),
    // поэтому по ней нельзя понять, новый это пользователь или нет.
    let purpose: 'login' | 'register' = 'register';
    try {
      try {
        await sendCode('register');
      } catch(err: unknown) {
        if(!(err instanceof Error) || err.message !== 'Phone number is already registered') throw err;
        purpose = 'login';
        await sendCode('login');
      }

      onCodeSent(phone, purpose);
    } catch(err: unknown) {
      const message = err instanceof Error ? err.message : 'Ошибка отправки кода.';
      // код уже отправлен недавно и ещё действует — пускаем вводить его
      if(message === 'Code was sent recently, try again later') {
        onCodeSent(phone, purpose);
        return;
      }
      setError(translateError(message));
    } finally {
      setIsLoading(false);
    }
  };


  const sendCode = async (purpose: 'login' | 'register') => {
    const data = await sendOtp(`+996${phone}`, purpose);
    // в режиме разработки приходит debug_code
    if(data.debug_code) {
      // %c - стандартный спецификатор форматирования в браузерных консолях (сделает код более видным)
      // он говорит браузеру: "Примени стили, идущие следующим аргументом, к предстоящему тексту"
      console.log('%c[SMS CODE]: ' + data.debug_code, 'color: #fec200; font-size: 16px; font-weight: bold;');
      alert(`Тестовый режим! Ваш код: ${data.debug_code}`);
    }
  };


  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-tg-hint text-sm mb-2">
          Номер телефона
        </label>

        <div className="flex items-stretch rounded-xl bg-white/5 border border-white/10 overflow-hidden focus-within:border-brand/50 transition-colors">
          <span className="px-3 flex items-center text-tg-hint text-sm border-r border-white/10">
            +996
          </span>

          <input
            type="tel"
            inputMode="numeric"
            value={phone}
            onChange={(e) => setPhone(e.target.value.replace(/\D/g, '').slice(0, 9))}
            placeholder="555 123 456"
            className="flex-1 bg-transparent px-3 py-3 text-tg-text outline-none text-base"
          />
        </div>

        {error && (
          <p className="text-red-400 text-xs mt-2">{error}</p>
        )}
      </div>


      <label className="flex items-start gap-2 text-xs text-tg-hint cursor-pointer">
        <input
          type="checkbox"
          checked={agree}
          onChange={(e) => setAgree(e.target.checked)}
          className="mt-0.5 accent-brand"
        />
        <span>
          Даю согласие с <a href="#" className="text-brand underline">условиями</a> и {' '}
          <a href="#" className="text-brand underline">политикой конфиденциальности</a>
        </span>
      </label>

      <button
        type="submit"
        disabled={isLoading} // блок кнопки во время текущего запроса
        className="btn btn-fancy w-full py-3 text-base font-bold disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isLoading ? 'Отправка...' : 'Получить код'}
      </button>
    </form>
  );
}