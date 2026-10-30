// DOM
const phoneInput = document.getElementById('phoneInput');
const phoneError = document.getElementById('phoneError');
const requestCodeBtn = document.getElementById('requestCodeBtn');

const smsStep = document.getElementById('smsStep');
const smsInput = document.getElementById('smsInput');
const smsError = document.getElementById('smsError');
const submitBtn = document.getElementById('submitBtn');
const changePhoneBtn = document.getElementById('changePhoneBtn');

const timerContainer = document.getElementById('timerContainer');
const timerElement = document.getElementById('timer');
const resendBtn = document.getElementById('resendBtn');
const loginForm = document.getElementById('loginForm');

// Вход по паролю и восстановление пароля
const loginTitle = document.getElementById('loginTitle');
const loginTabs = document.getElementById('loginTabs');
const tabButtons = loginTabs.querySelectorAll('.login-tab');

const passwordStep = document.getElementById('passwordStep');
const passwordInput = document.getElementById('passwordInput');
const passwordError = document.getElementById('passwordError');
const passwordLoginBtn = document.getElementById('passwordLoginBtn');
const forgotPasswordBtn = document.getElementById('forgotPasswordBtn');
const backToPasswordBtn = document.getElementById('backToPasswordBtn');

const newPasswordGroup = document.getElementById('newPasswordGroup');
const newPasswordInput = document.getElementById('newPasswordInput');
const newPasswordRepeat = document.getElementById('newPasswordRepeat');
const newPasswordError = document.getElementById('newPasswordError');

let TimerCD;

// sms - вход по коду, password - по паролю, reset - новый пароль по коду
let mode = 'sms';


// Валидация номера телефона (9 цифр)
function validatePhone(phone) {
  const phoneRegex = /^\d{9}$/;

  return phoneRegex.test(phone.trim());
}

// Ограничение ввода только цифр в поле номера телефона
phoneInput.addEventListener('input', (event) => {
  event.target.value = event.target.value.replace(/\D/g, ''); // удаляем все нецифровые символы
});

// Проверка номера перед запросом, ошибка - под полем номера
function checkPhone() {
  phoneError.textContent = ''; // очищаем сообщение об ошибке
  phoneInput.parentElement.classList.remove('input-error');

  if (!validatePhone(phoneInput.value)) {
    phoneError.textContent = 'Введите корректный номер телефона (9 цифр)';
    phoneInput.parentElement.classList.add('input-error');

    return false;
  }

  return true;
}


// Номер в формате бэкенда: +996XXXXXXXXX
function fullPhone() {
  return '+996' + phoneInput.value.trim();
}

// Код для входа или для смены пароля
function otpPurpose() {
  return mode === 'reset' ? 'reset_password' : 'login';
}

// Запрос SMS-кода, возвращает задержку до повторной отправки
async function sendCode() {
  const data = await api.request('auth', '/api/v1/auth/otp/send', {
    method: 'POST',
    body: { phone: fullPhone(), purpose: otpPurpose() },
    auth: false
  });

  // В dev-окружении бэкенд возвращает код в ответе
  if(data.debug_code) ui.toast(`Код (dev): ${data.debug_code}`, 'info', 10000);

  return data.resend_after;
}


// Переключение режима формы
function setMode(newMode) {
  mode = newMode;

  // шаг ввода кода сбрасываем при любой смене режима
  resetSmsStep();

  tabButtons.forEach(b => b.classList.toggle('active', b.dataset.mode === newMode));
  loginTabs.classList.toggle('hidden', newMode === 'reset');
  loginTitle.textContent = newMode === 'reset' ? 'Восстановление пароля' : 'Вход в админ-панель';

  passwordStep.classList.toggle('hidden', newMode !== 'password');
  requestCodeBtn.classList.toggle('hidden', newMode === 'password');
  newPasswordGroup.classList.toggle('hidden', newMode !== 'reset');
  backToPasswordBtn.classList.toggle('hidden', newMode !== 'reset');
  submitBtn.textContent = newMode === 'reset' ? 'Сохранить пароль и войти' : 'Войти';

  passwordError.textContent = '';
  passwordInput.classList.remove('input-error');

  // способ входа запоминаем (восстановление - разовое действие)
  if(newMode !== 'reset') {
    try { localStorage.setItem('loginMode', newMode); } catch {}
  }
}

tabButtons.forEach(btn => btn.addEventListener('click', () => setMode(btn.dataset.mode)));

forgotPasswordBtn.addEventListener('click', () => {
  setMode('reset');
  phoneInput.focus();
});

backToPasswordBtn.addEventListener('click', () => setMode('password'));


// Таймер (по умолчанию 60 секунд)
function startTimer(seconds = 60) {
  let timeLeft = seconds;

  timerElement.textContent = timeLeft;
  timerContainer.classList.remove('hidden');
  resendBtn.classList.add('hidden');

  clearInterval(TimerCD); // очистка предыдущего таймера, если был запущен

  TimerCD = setInterval(() => {
    timeLeft--;
    timerElement.textContent = timeLeft;

    if (timeLeft <= 0) {
      clearInterval(TimerCD); // остановка таймера
      timerContainer.classList.add('hidden'); // скрываем таймер
      resendBtn.classList.remove('hidden'); // показываем кнопку повторной отправки
    }
  }, 1000);
}


// Получение кода
requestCodeBtn.addEventListener('click', async () => { // async для возможности использовать await внутри функции
  const phoneValue = phoneInput.value;

  // Валидация ввода
  if (!checkPhone()) return; // прекращаем выполнение функции, если номер некорректный

  // Отправка запроса кода
  let resendAfter;
  requestCodeBtn.disabled = true;

  try {
    resendAfter = await sendCode();
  } catch (err) {
    phoneError.textContent = err.message;
    phoneInput.parentElement.classList.add('input-error');

    return;
  } finally {
    requestCodeBtn.disabled = false;
  }

  smsStep.classList.remove('hidden'); // при успешном запросе показываем ввод кода (скрыт по умолчанию)
  changePhoneBtn.classList.remove('hidden');
  requestCodeBtn.classList.add('hidden'); // скрываем кнопку запроса кода
  phoneInput.disabled = true; // блокируем ввод номера при вводе кода

  startTimer(resendAfter);
  smsInput.focus();

  ui.toast(`Код отправлен на +996 ${phoneValue}`, 'success');
});


// Ограничение ввода нецифровых символов
smsInput.addEventListener('input', (event) => {
  event.target.value = event.target.value.replace(/\D/g, '');
});


// Повторная отправка кода
resendBtn.addEventListener('click', async () => {
  try {
    startTimer(await sendCode()); // перезапуск таймера
  } catch (err) {
    ui.toast(err.message, 'error');

    return;
  }

  ui.toast('Код отправлен повторно', 'success');
});


// Возврат к вводу номера
function resetSmsStep() {
  phoneInput.disabled = false;

  smsStep.classList.add('hidden');
  smsInput.value = '';
  smsError.textContent = '';
  smsInput.classList.remove('input-error');

  newPasswordInput.value = '';
  newPasswordRepeat.value = '';
  newPasswordError.textContent = '';

  requestCodeBtn.classList.toggle('hidden', mode === 'password');
  changePhoneBtn.classList.add('hidden');

  clearInterval(TimerCD);
}

// разблокировка кнопки смены номера
changePhoneBtn.addEventListener('click', () => {
  resetSmsStep();
  phoneInput.focus();
});


// Номера нет в системе - ошибка относится к номеру, а не к коду или паролю
function showUnknownPhone() {
  if(mode !== 'password') resetSmsStep();

  phoneError.textContent = 'Номер не зарегистрирован. Обратитесь к владельцу заведения';
  phoneInput.parentElement.classList.add('input-error');
}


// Сессия -> в панель (только администраторы и владелец)
function finishLogin(session, showError) {
  if(!api.ADMIN_ROLES.includes(session.user.role)) {
    api.clearSession();
    showError('Нет доступа к админ-панели');

    return;
  }

  api.saveSession(session);
  window.location.href = '../main-menu/main.html';
}


// Пароль по правилам бэкенда: 8-72 символа, буквы и цифры
function passwordProblem(password) {
  if(password.length < 8) return 'Пароль должен быть не короче 8 символов';
  if(new TextEncoder().encode(password).length > 72) return 'Пароль слишком длинный';
  if(!/[A-Za-zА-Яа-яЁё]/.test(password) || !/\d/.test(password)) return 'Пароль должен содержать буквы и цифры';

  return null;
}


// Вход по номеру и паролю
async function loginWithPassword() {
  passwordError.textContent = '';
  passwordInput.classList.remove('input-error');

  if(!checkPhone()) return;

  const showError = (message) => {
    passwordError.textContent = message;
    passwordInput.classList.add('input-error');
  };

  if(!passwordInput.value) {
    showError('Введите пароль');

    return;
  }

  passwordLoginBtn.disabled = true;

  try {
    const session = await api.request('auth', '/api/v1/auth/login', {
      method: 'POST',
      body: { phone: fullPhone(), password: passwordInput.value },
      auth: false
    });

    finishLogin(session, showError);
  } catch (err) {
    showError(err.message);
  } finally {
    passwordLoginBtn.disabled = false;
  }
}


// Вход по коду или новый пароль по коду
async function loginWithCode() {
  const smsValue = smsInput.value.trim();
  smsError.textContent = '';
  smsInput.classList.remove('input-error');
  newPasswordError.textContent = '';

  const showError = (message) => {
    smsError.textContent = message;
    smsInput.classList.add('input-error');
  };

  // валидация кода (4-8 цифр, сейчас бэкенд шлёт 6)
  if (!/^\d{4,8}$/.test(smsValue)) {
    showError('Введите корректный код');

    return;
  }

  const newPassword = newPasswordInput.value;

  if(mode === 'reset') {
    const problem = passwordProblem(newPassword);

    if(problem || newPassword !== newPasswordRepeat.value) {
      newPasswordError.textContent = problem || 'Пароли не совпадают';

      return;
    }
  }

  submitBtn.disabled = true;

  try {
    // код -> одноразовый verification_token
    const { verification_token } = await api.request('auth', '/api/v1/auth/otp/verify', {
      method: 'POST',
      body: { phone: fullPhone(), code: smsValue, purpose: otpPurpose() },
      auth: false
    });

    let session;

    if(mode === 'reset') {
      // новый пароль, затем вход с ним (старые сессии бэкенд завершает)
      await api.request('auth', '/api/v1/auth/password/reset', {
        method: 'POST',
        body: { verification_token, new_password: newPassword },
        auth: false
      });

      session = await api.request('auth', '/api/v1/auth/login', {
        method: 'POST',
        body: { phone: fullPhone(), password: newPassword },
        auth: false
      });

      ui.toast('Пароль изменён', 'success');
    } else {
      session = await api.request('auth', '/api/v1/auth/login', {
        method: 'POST',
        body: { verification_token },
        auth: false
      });
    }

    finishLogin(session, showError);
  } catch (err) {
    // код верный, но номера нет в системе
    if(err.detail === 'User not found') {
      showUnknownPhone();

      return;
    }

    showError(err.message);
  } finally {
    submitBtn.disabled = false;
  }
}


// Отправка формы (вход)
loginForm.addEventListener('submit', async (e) => {
  e.preventDefault(); // предотвращаем перезагрузку страницы браузером

  if(mode === 'password') {
    await loginWithPassword();

    return;
  }

  // Enter на шаге ввода телефона - запрашиваем код, а не входим
  if(smsStep.classList.contains('hidden')) {
    requestCodeBtn.click();

    return;
  }

  await loginWithCode();
});


// Способ входа с прошлого раза
let savedMode = null;
try { savedMode = localStorage.getItem('loginMode'); } catch {}

setMode(savedMode === 'password' ? 'password' : 'sms');
