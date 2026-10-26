// Обертка для хранения токена
const TOKEN_KEY = 'pivnitsa_auth_token';
const REFRESH_TOKEN_KEY = 'pivnitsa_refresh_token';

// В TG используем CloudStorage (прописан в telegram.d.ts), в браузере - localStorage
const cloud = () => window.Telegram?.WebApp?.CloudStorage;


// общая функция для сохранения по ключу
async function setItem(key: string, value: string): Promise<void> {
  const cs = cloud();
  if(!cs) return localStorage.setItem(key, value);

  return new Promise((resolve) => {
    cs.setItem(key, value, () => resolve());
  });
}

// общая функция для получения по ключу
async function getItem(key: string): Promise<string | null> {
  const cs = cloud(); // cloud возвращает либо CloudStorage в TG, либо undefined в браузере
  if(!cs) return localStorage.getItem(key); // если CloudStorage нет, используем localStorage (fallback для разработки в браузере)

  // getItem, setItem, removeItem в CloudStorage работают ассинхронно через коллбэки
  // оборачиваем каждый в Promise, чтобы можно было await
  return new Promise((resolve) => {
    cs.getItem(key, (err, value) => {
      resolve(err ? null : value);
    });
  });
}

// общая функция для удаления
async function removeItem(key: string): Promise<void> {
  const cs = cloud();
  if(!cs) return localStorage.removeItem(key);

  return new Promise((resolve) => {
    cs.removeItem(key, () => resolve());
  });
}


export const authStorage = {
  // access token - быстро истекает
  async getToken(): Promise<string | null> {
    return getItem(TOKEN_KEY);
  },

  async setToken(token: string): Promise<void> {
    return setItem(TOKEN_KEY, token);
  },


  // refresh token - долго истекает
  async getRefreshToken(): Promise<string | null> {
    return getItem(REFRESH_TOKEN_KEY);
  },

  async setRefreshToken(token: string): Promise<void> {
    return setItem(REFRESH_TOKEN_KEY, token);
  },


  // очистка - при выходе или истечении сессии
  async clear(): Promise<void> {
    await removeItem(TOKEN_KEY);
    await removeItem(REFRESH_TOKEN_KEY);
  }
};