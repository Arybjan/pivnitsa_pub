import { useState } from "react";
import { PhoneStep } from "./PhoneStep";
import { CodeStep } from "./CodeStep";
import { PasswordStep } from "./PasswordStep"
import { loginByToken } from "../../api/auth";
import { useAuth } from "../../context/useAuth";


type Step = 'phone' | 'code' | 'password';

interface AuthSheetProps {
  onClose: () => void;
  onSuccess: () => void;
}


export function AuthSheet({ onClose, onSuccess }: AuthSheetProps) {
  const [step, setStep] = useState<Step>('phone');
  const [phone, setPhone] = useState('');
  const [purpose, setPurpose] = useState<'login' | 'register'>('register');
  const [verificationToken, setVerificationToken] = useState('');

  const { login } = useAuth();


  const handleVerifySuccess = async(token: string) => {
    if(purpose === 'register') {
      setVerificationToken(token);
      setStep('password');
    } else {
      try {
        const data = await loginByToken(token);
        await login(data.access_token, data.refresh_token, data.user);
        
        onSuccess();
      } catch(err: unknown) {
        const message = err instanceof Error ? err.message : '';
        console.error(message);
      }
    }
  };


  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-md bg-tg-secondary rounded-2xl p-6 animate-fade-in"
        onClick={(e) => e.stopPropagation()}
      >

        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-tg-text">
            {step === 'phone' ? 'Вход' : step === 'code' ? 'Введите код' : 'Создайте пароль'}
          </h2>

          <button
            type="button"
            onClick={onClose}
            aria-label='Закрыть'
            className="w-9 h-9 flex items-center justify-center rounded-full bg-white/5 text-tg-hint hover:bg-white/10 hover:text-tg-text transition-colors"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>


        {step === 'phone' && (
          <PhoneStep onCodeSent={(p, purp) => { setPhone(p); setPurpose(purp); setStep('code'); }} />
        )}

        {step === 'code' && (
          <CodeStep
            phone={phone}
            purpose={purpose}
            onBack={() => setStep('phone')}
            onVerifySuccess={handleVerifySuccess}
          />
        )}

        {step === 'password' && (
          <PasswordStep
            verificationToken={verificationToken}
            phone={phone}
            onSuccess={onSuccess}
          />
        )}

      </div>
    </div>
  );
}