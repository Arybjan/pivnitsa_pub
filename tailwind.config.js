/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Цвета Telegram (подстраиваются под тему юзера)
        tg: {
          bg: 'var(--tg-theme-bg-color, #0a0a0a)',
          secondary: 'var(--tg-theme-secondary-bg-color, #141414)',
          text: 'var(--tg-theme-text-color, #ffffff)',
          hint: 'var(--tg-theme-hint-color, #8a8a8a)',
          link: 'var(--tg-theme-link-color, #fec200)',
          button: 'var(--tg-theme-button-color, #fec200)',
          'button-text': 'var(--tg-theme-button-text-color, #000000)',
        },
        brand: {
          DEFAULT: '#fec200',
          hover: '#e0aa00',
        },
        table: {
          free: '#22c55e',
          booked: '#f59e0b',
          occupied: '#ef4444',
          disabled: '#94a3b8',
        },
      },
      fontFamily: {
        sans: [
          'system-ui',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'sans-serif',
        ],
      },
      keyframes: {
        'slide-up': {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'zoom-in': {
          '0%': { opacity: '0', transform: 'scale(0.96)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        'fade-in-up': {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'bounce-slow': {
          '0%, 100%': { transform: 'translateY(-5%)' },
          '50%': { transform: 'translateY(0)' },
        },
      },
      animation: {
        'slide-up': 'slide-up 0.3s ease-out',
        'fade-in': 'fade-in 0.2s ease-out',
        'zoom-in': 'zoom-in 0.2s ease-out',
        'fade-in-up': 'fade-in-up 0.4s ease-out both',
        'bounce-slow': 'bounce-slow 2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
