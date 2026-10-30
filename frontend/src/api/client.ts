import { authStorage } from "../lib/auth-storage";


export const API = {
  auth: import.meta.env.VITE_AUTH_URL || 'http://localhost:8001',
  booking: import.meta.env.VITE_BOOKING_URL || 'http://localhost:8002',
  venue: import.meta.env.VITE_VENUE_URL || 'http://localhost:8003',
  payment: import.meta.env.VITE_PAYMENT_URL || 'http://localhost:8004',
  notification: import.meta.env.VITE_NOTIFICATION_URL || 'http://localhost:8005',
  event: import.meta.env.VITE_EVENT_URL || 'http://localhost:8006',
};


interface RequestOptions extends RequestInit {
  token?: string | null;
}


export async function apiRequest<T>(url: string, options: RequestOptions = {}): Promise<T> {
  const { token, headers, ...rest } = options;

  const defaultHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if(token) defaultHeaders['Authorization'] = `Bearer ${token}`;


  try {
    const response = await fetch(url, {
      ...rest,
      headers: {
        ...defaultHeaders,
        ...headers,
      },
    });


    // пробуем обновить токен, если он истек
    if(response.status === 401 && token) {
      const refreshToken = await authStorage.getRefreshToken();
      if(refreshToken) {
        const refreshRes = await fetch(`${API.auth}/api/v1/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });

        if(refreshRes.ok) {
          const data = await refreshRes.json();
          await authStorage.setToken(data.access_token);
          await authStorage.setRefreshToken(data.refresh_token);

          // повторяем исходный запрос с новым токеном
          return apiRequest<T>(url, { ...options, token: data.access_token });
        }
      }

      // если обновить не удалось - чистим токены (выкидываем на экран входа)
      await authStorage.clear();
      throw new Error('Сессия истекла. Войдите заново.');
    }


    if(!response.ok) {
      let errorMessage = 'Ошибка запроса';
      try {
        const errorData = await response.json();

        if(errorData.detail) {
          if(typeof errorData.detail === 'string') errorMessage = errorData.detail;
          else if(Array.isArray(errorData.detail) && errorData.detail[0]?.msg) errorMessage = errorData.detail[0].msg;
          else errorMessage = JSON.stringify(errorData.detail);
        }
      } catch {
        // если тело не JSON, оставляем стандартный текст
      }

      throw new Error(errorMessage);
    }


    if(response.status === 204) return {} as T;

    return response.json();
  } catch (err: unknown) {
    // если это ошибка сети (fetch failed to connect)
    if(err instanceof TypeError && err.message === 'Failed to fetch') {
      // cause - прячет одну ошибку (стандартную) под другой (кастомной), что нужно для отладки
      throw new Error('Не удалось связаться с сервером. Проверьте интернет или попробуйте позже.', { cause: err });
    }
    // если это кастомная ошибка (из !response.ok) - дальше
    if(err instanceof Error) throw err;

    throw new Error('Неизвестная ошибка при запросе', { cause: err });
  }
}