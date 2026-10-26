import { useRef } from "react";
import { formatDateShort, todayISO, maxBookingDateISO } from "../../lib/date";


interface DatePickerProps {
  value: string;
  onChange: (date: string) => void;
}


export function DatePicker({ value, onChange }: DatePickerProps) {
  const today = todayISO();
  const maxDate = maxBookingDateISO();

  const isToday = value === today;
  const displayLabel = isToday ? 'Сегодня' : formatDateShort(value);

  // useRef - ссылка на input, чтобы "дернуть" его из btn
  const inputRef = useRef<HTMLInputElement>(null);

  const openPicker = () => {
    const input = inputRef.current;
    if (!input) return;

    if (typeof input.showPicker === "function") input.showPicker(); // showPicker() программно открывает системный календарь
    else input.click(); // если showPicker() недоступен из-за несовместимости браузера
  };


  return (
    <>
      <button
        type="button"
        onClick={openPicker}
        className="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-tg-secondary border border-white/5
                  text-sm font-semibold cursor-pointer hover:border-brand/40 transition-colors"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-brand">
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
          <line x1="16" y1="2" x2="16" y2="6" />
          <line x1="8" y1="2" x2="8" y2="6" />
          <line x1="3" y1="10" x2="21" y2="10" />
        </svg>

        <span>{displayLabel}</span>
      </button>

      <input
        ref={inputRef}
        type="date"
        value={value}
        min={today}
        max={maxDate}
        onChange={(e) => e.target.value && onChange(e.target.value)}
        aria-hidden="true"
        tabIndex={-1}
        className="sr-only"
      />
    </>
  );
}