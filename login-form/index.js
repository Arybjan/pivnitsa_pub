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

let TimerCD;


// Валидация номера телефона (9 цифр)
function validatePhone(phone) {
  const phoneRegex = /^\d{9}$/;

  return phoneRegex.test(phone.trim()); 
}

// Ограничение ввода только цифр в поле номера телефона
phoneInput.addEventListener('input', (event) => {
  event.target.value = event.target.value.replace(/\D/g, ''); // удаляем все нецифровые символы
});


// Таймер (60 секунд)
function startTimer() {
  let timeLeft = 60;

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

  phoneError.textContent = ''; // очищаем сообщение об ошибке
  phoneInput.parentElement.classList.remove('input-error');

  // Валидация ввода
  if (!validatePhone(phoneValue)) {
    phoneError.textContent = 'Введите корректный номер телефона (9 цифр)';
    phoneInput.parentElement.classList.add('input-error');

    return; // прекращаем выполнение функции, если номер некорректный
  }

  // Отправка запроса кода
  // backend

  smsStep.classList.remove('hidden'); // при успешном запросе показываем ввод кода (скрыт по умолчанию)
  changePhoneBtn.classList.remove('hidden');
  requestCodeBtn.classList.add('hidden'); // скрываем кнопку запроса кода
  phoneInput.disabled = true; // блокируем ввод номера при вводе кода

  startTimer();
});


// Ограничение ввода нецифровых символов
smsInput.addEventListener('input', (event) => {
  event.target.value = event.target.value.replace(/\D/g, '');
});


// Повторная отправка кода
resendBtn.addEventListener('click', () => {
  // backend fetch

  console.log('Повторная отправка SMS...');
  startTimer(); // перезапуск таймера
});


// разблокировка кнопки смены номера
changePhoneBtn.addEventListener('click', () => {
  phoneInput.disabled = false;
  phoneInput.focus();

  smsStep.classList.add('hidden');
  smsInput.value = '';
  smsError.textContent = '';
  smsInput.classList.remove('input-error');

  requestCodeBtn.classList.remove('hidden');
  changePhoneBtn.classList.add('hidden');

  clearInterval(TimerCD);
});


// Отправка формы (вход)
loginForm.addEventListener('submit', async (e) => {
  e.preventDefault(); // предотвращаем перезагрузку страницы браузером

  const smsValue = smsInput.value.trim();
  smsError.textContent = '';
  smsInput.classList.remove('input-error');

  // валидация кода (4 цифры)
  if (smsValue.length < 4) {
    smsError.textContent = 'Введите корректный код';
    smsInput.classList.add('input-error');

    return;
  }

  // backend

  window.location.href = '../main-menu/main.html';
});