// Общий клиент бэкенда: адреса сервисов, токены, обновление сессии
// await api.request('event', '/api/v1/events/all') -> JSON или null (204)
// api.requireAuth() - на защищённых страницах, отправляет на логин без токена
// Ошибки бросаются как ApiError { status, message, detail } - message на русском, detail - как прислал бэкенд

const api = (() => {
  // Адреса сервисов локального стенда (pivnitsa_dev/infra), можно переопределить через window.PIVNITSA_API
  const SERVICES = Object.assign({
    auth: 'http://localhost:8001',
    booking: 'http://localhost:8002',
    venue: 'http://localhost:8003',
    payment: 'http://localhost:8004',
    notification: 'http://localhost:8005',
    event: 'http://localhost:8006'
  }, window.PIVNITSA_API);

  const ADMIN_ROLES = ['admin', 'owner'];
  const LOGIN_PAGE = '../login-form/index.html';

  // Переводы частых ответов бэкенда
  const MESSAGES = {
    'Invalid code': 'Неверный код',
    'Code expired or not requested': 'Код истёк, запросите новый',
    'Too many invalid attempts, request a new code': 'Слишком много попыток, запросите новый код',
    'Code was sent recently, try again later': 'Код уже отправлен, попробуйте позже',
    'Too many codes requested, try again later': 'Слишком много запросов кода, попробуйте позже',
    'SMS delivery is temporarily unavailable': 'Не удалось отправить SMS, попробуйте позже',
    'User not found': 'Пользователь с таким номером не найден',
    'Account is deactivated': 'Аккаунт заблокирован',
    'Invalid phone or password': 'Неверный номер или пароль',
    'Too many failed login attempts': 'Слишком много неверных попыток входа',
    'Invalid or expired verification token': 'Код устарел, запросите новый',
    'Verification token already used': 'Код уже использован, запросите новый',
    'Phone number is already registered': 'Номер уже зарегистрирован',
    'Email is already in use': 'Этот email уже используется',
    'Conflicting hall name, table number or invalid data': 'Стол с таким номером уже есть в этом зале',
    'Venue management permission required': 'Нет прав на изменение схемы зала',
    'Table is already booked for this date': 'Стол уже забронирован на эту дату',
    'Table is already booked for this event': 'Стол уже забронирован на это мероприятие',
    'Table is already booked': 'Стол уже забронирован',
    'Only active bookings can be changed': 'Отменённую бронь изменить нельзя',
    'Booking cannot be cancelled': 'Бронь уже отменена',
    'Booking not found': 'Бронь не найдена',
    'Admin role required': 'Недостаточно прав'
  };

  class ApiError extends Error {
    constructor(status, message, detail = null) {
      super(message);
      this.status = status;
      this.detail = detail;
    }
  }


  // Хранилище сессии
  function read(key) {
    try { return localStorage.getItem(key); } catch { return null; }
  }

  function write(key, value) {
    try {
      if(value === null) localStorage.removeItem(key);
      else localStorage.setItem(key, value);
    } catch {}
  }

  function saveSession({ access_token, refresh_token, user }) {
    write('accessToken', access_token);
    write('refreshToken', refresh_token);

    if(user) {
      write('userRole', user.role);
      write('user', JSON.stringify(user));
    }
  }

  function clearSession() {
    ['accessToken', 'refreshToken', 'userRole', 'user'].forEach(key => write(key, null));
  }


  // Текст ошибки из ответа FastAPI ({ detail: строка | [{ msg }] })
  function errorMessage(status, body, headers) {
    const detail = body && body.detail;

    if(status === 429) {
      const retryAfter = headers.get('Retry-After');
      const base = MESSAGES[detail] || 'Слишком много запросов';

      return retryAfter ? `${base} (через ${retryAfter} сек.)` : base;
    }

    if(typeof detail === 'string') return MESSAGES[detail] || detail;
    if(Array.isArray(detail) && detail.length) return 'Проверьте данные: ' + detail.map(d => d.msg).join('; ');
    if(status === 401) return 'Сессия истекла, войдите снова';
    if(status === 403) return 'Недостаточно прав';

    return `Ошибка сервера (${status})`;
  }


  // Один запрос на обновление токена, даже если 401 пришёл сразу нескольким запросам
  let refreshing = null;

  function refreshSession() {
    const refresh_token = read('refreshToken');
    if(!refresh_token) return Promise.resolve(false);

    refreshing = refreshing || fetch(`${SERVICES.auth}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token })
    })
      .then(async res => {
        if(!res.ok) return false;

        saveSession(await res.json());
        return true;
      })
      .catch(() => false)
      .finally(() => { refreshing = null; });

    return refreshing;
  }


  async function request(service, path, { method = 'GET', body, auth = true, retry = true } = {}) {
    const headers = {};
    if(body !== undefined) headers['Content-Type'] = 'application/json';

    const token = read('accessToken');
    if(auth && token) headers['Authorization'] = `Bearer ${token}`;

    let res;
    try {
      res = await fetch(SERVICES[service] + path, {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined
      });
    } catch {
      throw new ApiError(0, 'Сервер недоступен, проверьте подключение');
    }

    // Access-токен живёт 15 минут - обновляем и повторяем запрос один раз
    if(res.status === 401 && auth && retry && await refreshSession()) {
      return request(service, path, { method, body, auth, retry: false });
    }

    if(res.status === 401 && auth) {
      clearSession();
      window.location.href = LOGIN_PAGE;
    }

    if(res.status === 204) return null;

    const data = await res.json().catch(() => null);
    if(!res.ok) throw new ApiError(res.status, errorMessage(res.status, data, res.headers), data && data.detail);

    return data;
  }


  // Защищённые страницы: без сессии или без роли админа - на логин
  function requireAuth() {
    if(!read('accessToken') || !ADMIN_ROLES.includes(read('userRole'))) {
      clearSession();
      window.location.replace(LOGIN_PAGE);
    }
  }

  async function logout() {
    const refresh_token = read('refreshToken');

    if(refresh_token) {
      await request('auth', '/api/v1/auth/logout', { method: 'POST', body: { refresh_token }, auth: false }).catch(() => {});
    }

    clearSession();
    window.location.href = LOGIN_PAGE;
  }


  return { request, saveSession, clearSession, requireAuth, logout, ADMIN_ROLES, ApiError };
})();
