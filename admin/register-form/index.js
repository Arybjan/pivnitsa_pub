// DOM
const registerForm = document.getElementById('registerForm');

const phoneInput = document.getElementById('phoneInput');
const phoneError = document.getElementById('phoneError');
const changePhoneBtn = document.getElementById('changePhoneBtn');
const requestCodeBtn = document.getElementById('requestCodeBtn');

const detailsStep = document.getElementById('detailsStep');
const smsInput = document.getElementById('smsInput');
const smsError = document.getElementById('smsError');
const timerContainer = document.getElementById('timerContainer');
const timerElement = document.getElementById('timer');
const resendBtn = document.getElementById('resendBtn');

const firstNameInput = document.getElementById('firstNameInput');
const lastNameInput = document.getElementById('lastNameInput');
const nameError = document.getElementById('nameError');
const passwordInput = document.getElementById('passwordInput');
const passwordRepeat = document.getElementById('passwordRepeat');
const passwordError = document.getElementById('passwordError');
const submitBtn = document.getElementById('submitBtn');

const successStep = document.getElementById('successStep');
const loginLink = document.getElementById('loginLink');

let TimerCD;


// Номер в формате бэкенда: +996XXXXXXXXX
function fullPhone() {
  return '+996' + phoneInput.value.trim();
}

// только цифры в номере и коде
[phoneInput, smsInput].forEach(input => input.addEventListener('input', (event) => {
  event.target.value = event.target.value.replace(/\D/g, '');
}));


function showPhoneError(message) {
  phoneError.textContent = message;
  phoneInput.parentElement.classList.add('input-error');
}

// Пароль по правилам бэкенда: 8-72 символа, буквы и цифры
function passwordProblem(password) {
  if(password.length < 8) return 'Пароль должен быть не короче 8 символов';
  if(new TextEncoder().encode(password).length > 72) return 'Пароль слишком длинный';
  if(!/[A-Za-zА-Яа-яЁё]/.test(password) || !/\d/.test(password)) return 'Пароль должен содержать буквы и цифры';

  return null;
}


// Таймер повторной отправки кода
function startTimer(seconds = 60) {
  let timeLeft = seconds;

  timerElement.textContent = timeLeft;
  timerContainer.classList.remove('hidden');
  resendBtn.classList.add('hidden');

  clearInterval(TimerCD);

  TimerCD = setInterval(() => {
    timeLeft--;
    timerElement.textContent = timeLeft;

    if(timeLeft <= 0) {
      clearInterval(TimerCD);
      timerContainer.classList.add('hidden');
      resendBtn.classList.remove('hidden');
    }
  }, 1000);
}


// Код подтверждения номера, возвращает задержку до повторной отправки
async function sendCode() {
  const data = await api.request('auth', '/api/v1/auth/otp/send', {
    method: 'POST',
    body: { phone: fullPhone(), purpose: 'register' },
    auth: false
  });

  // В dev-окружении бэкенд возвращает код в ответе
  if(data.debug_code) ui.toast(`Код (dev): ${data.debug_code}`, 'info', 10000);

  return data.resend_after;
}


// Шаг 1: номер -> код
requestCodeBtn.addEventListener('click', async () => {
  phoneError.textContent = '';
  phoneInput.parentElement.classList.remove('input-error');

  if(!/^\d{9}$/.test(phoneInput.value.trim())) {
    showPhoneError('Введите корректный номер телефона (9 цифр)');

    return;
  }

  let resendAfter;
  requestCodeBtn.disabled = true;

  try {
    resendAfter = await sendCode();
  } catch (err) {
    showPhoneError(err.detail === 'Phone number is already registered'
      ? 'Номер уже зарегистрирован. Войдите в аккаунт'
      : err.message);

    return;
  } finally {
    requestCodeBtn.disabled = false;
  }

  detailsStep.classList.remove('hidden');
  changePhoneBtn.classList.remove('hidden');
  requestCodeBtn.classList.add('hidden');
  phoneInput.disabled = true;

  startTimer(resendAfter);
  smsInput.focus();

  ui.toast(`Код отправлен на +996 ${phoneInput.value}`, 'success');
});


resendBtn.addEventListener('click', async () => {
  try {
    startTimer(await sendCode());
  } catch (err) {
    ui.toast(err.message, 'error');

    return;
  }

  ui.toast('Код отправлен повторно', 'success');
});


changePhoneBtn.addEventListener('click', () => {
  phoneInput.disabled = false;
  phoneInput.focus();

  detailsStep.classList.add('hidden');
  smsInput.value = '';
  smsError.textContent = '';

  requestCodeBtn.classList.remove('hidden');
  changePhoneBtn.classList.add('hidden');

  clearInterval(TimerCD);
});


// Шаг 2: код + имя + пароль -> аккаунт
async function register() {
  [smsError, nameError, passwordError].forEach(el => el.textContent = '');
  smsInput.classList.remove('input-error');

  const code = smsInput.value.trim();
  const firstName = firstNameInput.value.trim();
  const password = passwordInput.value;

  if(!/^\d{4,8}$/.test(code)) {
    smsError.textContent = 'Введите корректный код';
    smsInput.classList.add('input-error');

    return;
  }

  if(!firstName) {
    nameError.textContent = 'Укажите имя';

    return;
  }

  const problem = passwordProblem(password);
  if(problem || password !== passwordRepeat.value) {
    passwordError.textContent = problem || 'Пароли не совпадают';

    return;
  }

  submitBtn.disabled = true;

  try {
    const { verification_token } = await api.request('auth', '/api/v1/auth/otp/verify', {
      method: 'POST',
      body: { phone: fullPhone(), code, purpose: 'register' },
      auth: false
    });

    const session = await api.request('auth', '/api/v1/auth/register', {
      method: 'POST',
      body: {
        verification_token,
        password,
        first_name: firstName,
        last_name: lastNameInput.value.trim() || null
      },
      auth: false
    });

    // новый аккаунт без доступа к панели - сессию сразу закрываем
    await api.request('auth', '/api/v1/auth/logout', {
      method: 'POST',
      body: { refresh_token: session.refresh_token },
      auth: false
    }).catch(() => {});
  } catch (err) {
    if(err.detail === 'Phone number is already registered') {
      changePhoneBtn.click();
      showPhoneError('Номер уже зарегистрирован. Войдите в аккаунт');

      return;
    }

    smsError.textContent = err.message;
    smsInput.classList.add('input-error');

    return;
  } finally {
    submitBtn.disabled = false;
  }

  clearInterval(TimerCD);
  registerForm.classList.add('hidden');
  successStep.classList.remove('hidden');
  loginLink.textContent = 'Перейти ко входу';
}


registerForm.addEventListener('submit', async (e) => {
  e.preventDefault();

  // Enter на шаге номера - запрашиваем код
  if(detailsStep.classList.contains('hidden')) {
    requestCodeBtn.click();

    return;
  }

  await register();
});
