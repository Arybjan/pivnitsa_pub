// без сессии администратора - на страницу входа
api.requireAuth();

// Размер зала в координатах схемы (одинаков на любом экране, на экран схема масштабируется)
const HALL_WIDTH = 1000;
const HALL_HEIGHT = 600;

const MIN_ZOOM = 0.6; // меньше - столики на телефоне не читаются, дальше схема прокручивается
const MAX_ZOOM = 1.4;


// Инициализация Canvas
const canvas = new fabric.Canvas('hallCanvas', {
  backgroundColor: 'transparent',
  selection: false, // запрет выделения нескольких объектов
  allowTouchScrolling: true // на телефоне свайп по пустому месту прокручивает схему
});

const wrapper = document.querySelector('.canvas-wrapper');


// Вписываем схему в доступное место
function fitCanvasToWrapper() {
  if(wrapper.clientWidth === 0) return; // вкладка схемы скрыта

  const isMobile = window.matchMedia('(max-width: 900px)').matches;

  // 2px - рамка .canvas-container
  let zoom = (wrapper.clientWidth - 2) / HALL_WIDTH;

  // на мобильном высота подстраивается под схему, на десктопе схема вписывается целиком
  if(!isMobile) zoom = Math.min(zoom, (wrapper.clientHeight - 2) / HALL_HEIGHT);

  zoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom));

  canvas.setZoom(zoom);
  canvas.setDimensions({ width: HALL_WIDTH * zoom, height: HALL_HEIGHT * zoom });
}

new ResizeObserver(fitCanvasToWrapper).observe(wrapper);


// глобальный запрет выворачивания столиков наизнанку
fabric.Object.prototype.lockScalingFlip = true;
fabric.Object.prototype.noScaleResetX = true;


let currentFloor = 1;


// Дата в формате Г-М-Д по местному времени (toISOString сдвигает дату в UTC)
function toLocalDateString(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');

  return `${y}-${m}-${d}`;
}


// Размер стола на схеме при масштабе 1
const TABLE_WIDTH = 120;
const TABLE_HEIGHT = 80;

// Залы venue-сервиса: этаж 1 - первый зал, этаж 2 - второй
const FLOOR_NAMES = ['1 этаж', '2 этаж'];
let halls = [];

// Столы загружаются из venue-сервиса
let tablesData = [];

// Столы с несохранённым положением или размером (сохраняются кнопкой "Сохранить схему")
const dirtyLayout = new Set();

// Брони на выбранную дату (из booking-сервиса)
let reservationsData = [];

// Брони на дату в окне бронирования, если она отличается от выбранной
let modalReservations = null;

// Мероприятия (из event-сервиса): бронь бывает на мероприятие или на обычный вечер
let eventsData = [];

const ACTIVE_BOOKING = ['PENDING_PAYMENT', 'CONFIRMED'];

const BOOKING_STATUS_LABELS = {
  PENDING_PAYMENT: 'Ждёт оплаты',
  CONFIRMED: 'Активна',
  CANCELLED: 'Отменена',
  EXPIRED: 'Истекла'
};


// экранирование текста с сервера перед вставкой в HTML
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, ch => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[ch]);

// Телефоны Кыргызстана: в поле вводятся 9 цифр после +996, показываются как "555 123 456"
function formatLocalPhone(digits) {
  return digits.replace(/\D/g, '').slice(0, 9).replace(/^(\d{3})(\d{0,3})(\d{0,3}).*$/, (_, a, b, c) => [a, b, c].filter(Boolean).join(' '));
}

// "+996555123456" / "+996 555 123456" -> "555 123 456" для поля ввода
function phoneToLocal(phone) {
  const digits = String(phone || '').replace(/\D/g, '');

  return formatLocalPhone(digits.startsWith('996') ? digits.slice(3) : digits);
}

// для списка броней: "+996 555 123 456"
function formatPhone(phone) {
  const digits = String(phone || '').replace(/\D/g, '');

  return digits.length === 12 && digits.startsWith('996') ? `+996 ${formatLocalPhone(digits.slice(3))}` : (phone || '');
}

// "1500.00" -> "1 500", "1500.50" -> "1 500,50"
function formatPrice(price) {
  const value = Number(price);
  const digits = Number.isInteger(value) ? 0 : 2;

  return value.toLocaleString('ru-RU', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

// Значение для поля ввода: "1500.00" -> "1500", "1500.50" -> "1500.5", null -> ""
function priceInputValue(price) {
  return price === null || price === undefined ? '' : String(Number(price));
}

// "ЧЧ:ММ" по местному времени
function toLocalTime(iso) {
  const date = new Date(iso);

  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

function eventsOnDate(date) {
  return eventsData.filter(ev => toLocalDateString(new Date(ev.starts_at)) === date);
}

// BookingResponse -> формат списка и схемы
function reservationFromApi(b) {
  const event = eventsData.find(ev => ev.id === b.event_id);
  const startsAt = b.starts_at || (event && event.starts_at);

  return {
    id: String(b.id),
    tableId: String(b.table_id),
    eventId: b.event_id,
    eventTitle: event ? event.title : (b.event_id ? `Мероприятие #${b.event_id}` : ''),
    date: b.booking_date || (startsAt ? toLocalDateString(new Date(startsAt)) : ''),
    time: startsAt ? toLocalTime(startsAt) : '',
    guestName: b.guest_name || 'Гость из приложения',
    guestPhone: formatPhone(b.phone),
    guestsCount: b.guests,
    totalAmount: Number(b.total_amount) || 0,
    prepayment: Number(b.prepayment) || 0,
    // бронь из приложения подтверждается после онлайн-оплаты
    paymentStatus: b.prepayment_paid || (b.source === 'APP' && b.status === 'CONFIRMED') ? 'paid' : 'unpaid',
    status: ACTIVE_BOOKING.includes(b.status) ? 'active' : 'cancelled',
    apiStatus: b.status,
    source: b.source,
    cancelReason: b.cancel_reason || '',
    comment: b.comment || '',
    // номер из Booking (через Venue) - остаётся и у удалённого стола
    tableNumber: b.table_number ?? null
  };
}


// Все мероприятия (бэкенд отдаёт максимум 100 за запрос)
async function loadEvents() {
  const items = [];
  let offset = 0;
  let page;

  do {
    page = await api.request('event', `/api/v1/events/all?limit=100&offset=${offset}`);
    items.push(...page.items);
    offset += page.items.length;
  } while(page.has_next && page.items.length);

  eventsData = items;
}

// Брони на дату: на обычный вечер (по дате) + на мероприятия этого дня (по event_id)
async function fetchReservations(date) {
  const requests = [api.request('booking', `/api/v1/bookings?date_from=${date}&date_to=${date}`)];

  const eventIds = eventsOnDate(date).map(ev => ev.id);
  if(eventIds.length) {
    requests.push(api.request('booking', '/api/v1/bookings?' + eventIds.map(id => `event_id=${id}`).join('&')));
  }

  const byId = new Map();
  (await Promise.all(requests)).flat().forEach(b => byId.set(b.id, b));

  return [...byId.values()].map(reservationFromApi).filter(r => r.date === date);
}

async function loadReservations() {
  const date = dateFilter.value;

  try {
    const items = await fetchReservations(date);
    if(date === dateFilter.value) reservationsData = items; // пока грузили, дату могли сменить
  } catch (err) {
    ui.toast(`Брони не загрузились: ${err.message}`, 'error');
  }
}


// Координаты на бэкенде - доли схемы зала (0..1), на канвасе - точки схемы HALL_WIDTH x HALL_HEIGHT
const clamp01 = (value) => Math.min(1, Math.max(0, value));

function floorOfHall(hallId) {
  return halls.findIndex(h => h.id === hallId) + 1;
}

function hallOfFloor(floor) {
  return halls[floor - 1];
}

// TableRead с бэкенда -> формат схемы
function tableFromApi(t) {
  return {
    id: String(t.id),
    floor: floorOfHall(t.hall_id),
    number: String(t.number),
    capacity: t.capacity,
    price: t.price ?? null,
    // недоступен и занят хранятся на сервере, свободен / забронирован считается по броням
    status: t.status === 'UNAVAILABLE' ? 'disabled' : t.occupied ? 'occupied' : 'free',
    x: t.x * HALL_WIDTH,
    y: t.y * HALL_HEIGHT,
    scaleX: t.width ? t.width * HALL_WIDTH / TABLE_WIDTH : 1,
    scaleY: t.height ? t.height * HALL_HEIGHT / TABLE_HEIGHT : 1,

    // последнее сохранённое на сервере - для отката при ошибке
    saved: { number: String(t.number), capacity: t.capacity, price: t.price ?? null, disabled: t.status === 'UNAVAILABLE', occupied: t.occupied }
  };
}

// положение и размер стола -> поля бэкенда
function layoutToApi(t) {
  const isDefaultSize = Math.abs(t.scaleX - 1) < 0.001 && Math.abs(t.scaleY - 1) < 0.001;

  return {
    x: clamp01(t.x / HALL_WIDTH),
    y: clamp01(t.y / HALL_HEIGHT),
    width: isDefaultSize ? null : clamp01(TABLE_WIDTH * t.scaleX / HALL_WIDTH),
    height: isDefaultSize ? null : clamp01(TABLE_HEIGHT * t.scaleY / HALL_HEIGHT)
  };
}


// Залы: берём первые два, недостающие создаём (на свежей базе их нет)
async function loadHalls() {
  halls = (await api.request('venue', '/api/v1/halls?limit=200')).sort((a, b) => a.id - b.id);

  for(let i = halls.length; i < FLOOR_NAMES.length; i++) {
    halls.push(await api.request('venue', '/api/v1/halls', {
      method: 'POST',
      body: { name: FLOOR_NAMES[i], map_width: HALL_WIDTH, map_height: HALL_HEIGHT }
    }));
  }

  halls = halls.slice(0, FLOOR_NAMES.length);
}

// Все столы обоих залов (бэкенд отдаёт максимум 200 за запрос)
async function loadTables() {
  const items = [];

  for(const hall of halls) {
    let page;
    let offset = 0;

    do {
      page = await api.request('venue', `/api/v1/tables?hall_id=${hall.id}&limit=200&offset=${offset}`);
      items.push(...page);
      offset += page.length;
    } while(page.length === 200);
  }

  tablesData = items.map(tableFromApi);
}


// Общий DOM
const noSelectionText = document.getElementById('noSelectionText');
const tablePropsForm = document.getElementById('tablePropsForm');
const propNumber = document.getElementById('propNumber');
const propCapacity = document.getElementById('propCapacity');
const propStatus = document.getElementById('propStatus');
const propPrice = document.getElementById('propPrice');

const viewCanvasBtn = document.getElementById('viewCanvasBtn');
const viewReservationsBtn = document.getElementById('viewReservationsBtn');

const canvasHeaderControls = document.getElementById('canvasHeaderControls');
const canvasView = document.getElementById('canvasView');
const reservationsSection = document.getElementById('reservationsSection');

const dateFilter = document.getElementById('reservationDateFilter');
dateFilter.value = toLocalDateString(new Date());

const reservationSearch = document.getElementById('reservationSearch');

// Бронь выбранного стола в боковой панели
const tableBookingInfo = document.getElementById('tableBookingInfo');
const tableBookingText = document.getElementById('tableBookingText');
const bookTableBtn = document.getElementById('bookTableBtn');
const openTableBookingBtn = document.getElementById('openTableBookingBtn');


// Запоминаем вкладку и этаж между заходами на страницу
function savePreference(key, value) {
  try { localStorage.setItem(key, value); } catch {}
}

function loadPreference(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}


// Дата для людей: "13 октября"
function formatDateHuman(dateString) {
  return new Date(dateString + 'T00:00').toLocaleDateString('ru', { day: 'numeric', month: 'long' });
}



// Переключение вкладок и этажей
function showCanvasView() {
  viewCanvasBtn.classList.add('active');
  viewReservationsBtn.classList.remove('active');

  canvasHeaderControls.classList.remove('hidden');
  canvasView.classList.remove('hidden');
  reservationsSection.classList.add('hidden');

  savePreference('hallView', 'canvas');
  fitCanvasToWrapper();
  renderFloor(currentFloor);
}

function showReservationsView() {
  viewReservationsBtn.classList.add('active');
  viewCanvasBtn.classList.remove('active');

  canvasHeaderControls.classList.add('hidden');
  canvasView.classList.add('hidden');
  reservationsSection.classList.remove('hidden');

  savePreference('hallView', 'reservations');
  renderReservations(); // обновляем таблицу при открытии вкладки
}

viewCanvasBtn.addEventListener('click', showCanvasView);
viewReservationsBtn.addEventListener('click', showReservationsView);



// Переключение этажей
const floor1Btn = document.getElementById('floor1Btn');
const floor2Btn = document.getElementById('floor2Btn');

function setFloor(floorNumber) {
  currentFloor = floorNumber;

  floor1Btn.classList.toggle('active', floorNumber === 1);
  floor2Btn.classList.toggle('active', floorNumber === 2);

  savePreference('hallFloor', floorNumber);
  renderFloor(floorNumber);
}

floor1Btn.addEventListener('click', () => setFloor(1));
floor2Btn.addEventListener('click', () => setFloor(2));



// Цвет по статусу столика
function getStatusColor(status) {
  switch (status) {
    case 'free': return '#22c55e';
    case 'booked': return '#f59e0b';
    case 'occupied': return '#ef4444';
    default: return '#94a3b8';
  }
}



// Отрисовка одного столика (прямоугольник и текст)
function createTableObject(tableData) {
  const rect = new fabric.Rect({
    width: 120,
    height: 80,

    fill: getStatusColor(tableData.status),

    // скругление углов
    rx: 8,
    ry: 8,

    // обводка
    stroke: '#ffffff',
    strokeWidth: 1,

    // точки привязки
    originX: 'center',
    originY: 'center'
  });

  // Надпись внутри столика
  const text = new fabric.Text(`№${tableData.number}\n(${tableData.capacity} чел)`, {
    fontSize: 14,
    fontFamily: 'system-ui, sans-serif',

    textAlign: 'center',

    fill: '#ffffff',

    originX: 'center',
    originY: 'center',

    selectable: false
  });

  // Объединяем прямоугольник и текст в единый перетаскиваемый объект
  const group = new fabric.Group([rect, text], {
    left: tableData.x,
    top: tableData.y,

    scaleX: tableData.scaleX || 1,
    scaleY: tableData.scaleY || 1,

    hasRotatingPoint: false,
    lockRotation: true,
    lockScalingFlip: true,
    minScaleLimit: 0.5,
    
    tableData: { ...tableData },
  });

  // оставляем только угловые ручки для пропорционального масштабирования
  group.setControlsVisibility({
    ml: false,
    mr: false,
    mt: false,
    mb: false,
    mtr: false
  });

  return group;
}



// Отрисовка всех столиков этажа
function renderFloor(floorNumber) {
  canvas.clear();
  canvas.setBackgroundColor('transparent', canvas.renderAll.bind(canvas));

  // clear() не вызывает selection:cleared - прячем панель свойств сами
  tablePropsForm.classList.add('hidden');
  tableBookingInfo.classList.add('hidden');
  noSelectionText.classList.remove('hidden');

  // фильтр столиков только для нужного этажа
  const floorTables = tablesData.filter(t => t.floor === floorNumber);

  floorTables.forEach(data => {
    const tableGroup = createTableObject(data);
    canvas.add(tableGroup);
  });

  updateCanvasColorsByDate();
  updateStats();
}



// Пересчет состояний для текущего этажа
function updateStats() {
  const currentTables = tablesData.filter(t => t.floor === currentFloor);

  const count = (status) => currentTables.filter(t => t.status === status).length;

  document.getElementById('statFreeCount').textContent = count('free');
  document.getElementById('statBookedCount').textContent = count('booked');
  document.getElementById('statOccupiedCount').textContent = count('occupied');
  document.getElementById('statDisabledCount').textContent = count('disabled');
  document.getElementById('statTotalSeats').textContent = currentTables.length;
}



// Выделение столиков и отображение свойств в боковой панели
canvas.on('selection:created', handleSelection);
canvas.on('selection:updated', handleSelection);

canvas.on('selection:cleared', () => {
  tablePropsForm.classList.add('hidden');
  tableBookingInfo.classList.add('hidden');
  noSelectionText.classList.remove('hidden');
});

function handleSelection(e) {
  const selectedObject = e.selected[0];

  // выбран ли столик
  if(selectedObject && selectedObject.tableData) {
    const data = selectedObject.tableData;

    propNumber.value = data.number;
    propCapacity.value = data.capacity;
    propPrice.value = priceInputValue(data.price);
    propStatus.value = data.status;

    noSelectionText.classList.add('hidden');
    tablePropsForm.classList.remove('hidden');

    refreshTableBookingInfo();
  }
}



// Активная бронь столика на дату
function getTableBooking(tableId, date = dateFilter.value) {
  return reservationsData.find(r => r.tableId === tableId && r.date === date && r.status === 'active');
}


// Блок брони выбранного стола в боковой панели
function refreshTableBookingInfo() {
  const activeObject = canvas.getActiveObject();
  if(!activeObject || !activeObject.tableData) {
    tableBookingInfo.classList.add('hidden');

    return;
  }

  const table = activeObject.tableData;
  const booking = getTableBooking(table.id);
  const dateText = formatDateHuman(dateFilter.value);

  propStatus.value = table.status; // статус мог смениться автоматически (бронь, отмена, другая дата)

  tableBookingInfo.classList.remove('hidden');

  if(booking) {
    tableBookingText.textContent = `Бронь на ${dateText}: ${booking.time}, ${booking.guestName}, ${booking.guestsCount} чел.`;
    openTableBookingBtn.classList.remove('hidden');
    bookTableBtn.classList.add('hidden');
  } else if(table.status === 'disabled') {
    tableBookingText.textContent = 'Стол недоступен для бронирования.';
    openTableBookingBtn.classList.add('hidden');
    bookTableBtn.classList.add('hidden');
  } else {
    tableBookingText.textContent = `Свободен на ${dateText}.`;
    openTableBookingBtn.classList.add('hidden');
    bookTableBtn.classList.remove('hidden');
  }
}


// Бронь по столику: открыть существующую или создать новую
function bookOrOpenTable(table) {
  const booking = getTableBooking(table.id);

  if(booking) {
    openEditModal(booking.id);
  } else if(table.status === 'disabled') {
    ui.toast(`Стол №${table.number} недоступен для бронирования`, 'warning');
  } else {
    openNewReservationModal(table);
  }
}

bookTableBtn.addEventListener('click', () => {
  const activeObject = canvas.getActiveObject();
  if(activeObject && activeObject.tableData) bookOrOpenTable(activeObject.tableData);
});

openTableBookingBtn.addEventListener('click', () => {
  const activeObject = canvas.getActiveObject();
  if(activeObject && activeObject.tableData) bookOrOpenTable(activeObject.tableData);
});

canvas.on('mouse:dblclick', (e) => {
  if(e.target && e.target.tableData) bookOrOpenTable(e.target.tableData);
});



// Стол, свойства которого правят в панели. Запоминаем при вводе: к событию change
// (потеря фокуса) клик по схеме уже может снять выделение
let editedTableObject = null;

// Изменение свойств столика в боковой панели
function updateActiveTable() {
  const activeObject = canvas.getActiveObject();
  if(!activeObject || !activeObject.tableData) return;

  editedTableObject = activeObject;

  const selectedDate = dateFilter.value;
  const hasActiveBooking = reservationsData.some(r =>
    r.tableId === activeObject.tableData.id && r.date === selectedDate && r.status === 'active'
  );


  // проверяем изменение статуса
  if(propStatus.value !== activeObject.tableData.status) {
    if(propStatus.value === 'booked' && !hasActiveBooking) {
      ui.toast('Статус «Забронирован» ставится автоматически при создании брони', 'warning');
      propStatus.value = activeObject.tableData.status; // возвращаем прежний статус
    }

    if (hasActiveBooking && (propStatus.value === 'free' || propStatus.value === 'disabled')) {
      ui.toast('На этот стол есть бронь. Сначала отмените или перенесите её', 'warning');
      propStatus.value = 'booked';
  
      return;
    }
  }


  // пока поле вместимости пустое (пользователь печатает) - оставляем прежнее значение
  const capacity = Number(propCapacity.value) > 0 ? Number(propCapacity.value) : activeObject.tableData.capacity;

  activeObject.tableData.number = propNumber.value;
  activeObject.tableData.capacity = capacity;
  activeObject.tableData.status = propStatus.value;

  const found = tablesData.find(t => t.id === activeObject.tableData.id);
  if(found) {
    found.number = propNumber.value;
    found.capacity = capacity;
    found.status = propStatus.value;
  }

  // обновляем визуал (цвет и текст внутри группы)
  const rect = activeObject.item(0);
  const text = activeObject.item(1);

  rect.set('fill', getStatusColor(propStatus.value));
  text.set('text', `№${propNumber.value}\n(${capacity} чел)`);

  canvas.renderAll(); // перерисовка Canvas
  updateStats();
  refreshTableBookingInfo();
}

// Сохранение номера, вместимости и доступности стола на сервере
async function persistTableProps() {
  const activeObject = editedTableObject;
  editedTableObject = null;
  if(!activeObject || !activeObject.tableData) return;

  const data = activeObject.tableData;
  const saved = data.saved;
  const patch = {};

  const number = Number(data.number);
  if(data.number !== saved.number) {
    if(!Number.isInteger(number) || number <= 0) {
      ui.toast('Номер стола - целое число больше нуля', 'error');
      revertTableProps(activeObject);

      return;
    }

    patch.number = number;
  }

  if(data.capacity !== saved.capacity) patch.capacity = data.capacity;

  // пустое поле - цена не задана (null)
  const priceText = propPrice.value.trim();
  const price = priceText === '' ? null : Number(priceText);
  if(price !== null && !/^\d{1,10}(\.\d{1,2})?$/.test(priceText)) {
    ui.toast('Цена - неотрицательное число, не больше двух знаков после запятой', 'error');
    revertTableProps(activeObject);

    return;
  }
  data.price = price === null ? null : price.toFixed(2);
  if(data.price !== saved.price) patch.price = data.price;

  // "Недоступен" - статус стола, "Занят" - отметка "гости за столом"
  const disabled = data.status === 'disabled';
  const occupied = data.status === 'occupied';
  if(disabled !== saved.disabled) patch.status = disabled ? 'UNAVAILABLE' : 'ACTIVE';
  if(occupied !== saved.occupied) patch.occupied = occupied;

  if(Object.keys(patch).length === 0) return;

  try {
    await api.request('venue', `/api/v1/tables/${data.id}`, { method: 'PATCH', body: patch });
  } catch (err) {
    ui.toast(err.message, 'error');
    revertTableProps(activeObject);

    return;
  }

  saved.number = data.number;
  saved.capacity = data.capacity;
  saved.price = data.price;

  // список столов (выбор стола в брони) берёт цену отсюда
  const found = tablesData.find(t => t.id === data.id);
  if(found) found.price = data.price;
  saved.disabled = disabled;
  saved.occupied = occupied;
}

// Откат свойств стола к сохранённым на сервере
function revertTableProps(obj) {
  const data = obj.tableData;
  const found = tablesData.find(t => t.id === data.id);

  data.number = data.saved.number;
  data.capacity = data.saved.capacity;
  data.price = data.saved.price;
  if(data.saved.disabled) data.status = 'disabled';
  else if(data.saved.occupied) data.status = 'occupied';
  else if(data.status === 'disabled' || data.status === 'occupied') data.status = 'free';

  if(found) Object.assign(found, { number: data.number, capacity: data.capacity, price: data.price, status: data.status });

  // панель показывает этот стол, только если он всё ещё выбран
  if(canvas.getActiveObject() === obj) {
    propNumber.value = data.number;
    propCapacity.value = data.capacity;
    propPrice.value = priceInputValue(data.price);
    propStatus.value = data.status;
  }

  obj.item(1).set('text', `№${data.number}\n(${data.capacity} чел)`);
  updateCanvasColorsByDate();
}

propNumber.addEventListener('input', updateActiveTable);
propCapacity.addEventListener('input', updateActiveTable);
propStatus.addEventListener('change', updateActiveTable);

propNumber.addEventListener('change', persistTableProps);
propCapacity.addEventListener('change', persistTableProps);
propStatus.addEventListener('change', persistTableProps);
propPrice.addEventListener('change', () => {
  editedTableObject = canvas.getActiveObject();
  persistTableProps();
});



// Первое свободное место на схеме (слева направо, сверху вниз), чтобы новые столы не ложились друг на друга
function findFreeSpot() {
  const WIDTH = 120;
  const HEIGHT = 80;
  const GAP = 20;

  const rects = canvas.getObjects().filter(o => o.tableData).map(o => o.getBoundingRect(true));

  for(let y = 40; y + HEIGHT <= HALL_HEIGHT; y += HEIGHT + GAP) {
    for(let x = 40; x + WIDTH <= HALL_WIDTH; x += WIDTH + GAP) {
      const overlaps = rects.some(r =>
        x < r.left + r.width + GAP && x + WIDTH + GAP > r.left &&
        y < r.top + r.height + GAP && y + HEIGHT + GAP > r.top
      );

      if(!overlaps) return { x, y };
    }
  }

  return { x: 40, y: 40 }; // места нет - кладем в угол
}


// Следующий номер на этаже (1, 2, 3... на первом, 201, 202... на втором)
function nextTableNumber(floor) {
  const numbers = tablesData
    .filter(t => t.floor === floor)
    .map(t => parseInt(t.number, 10))
    .filter(n => !isNaN(n));

  if(numbers.length === 0) return String(floor === 1 ? 1 : floor * 100 + 1);

  return String(Math.max(...numbers) + 1);
}


// Добавление столика
const addTableBtn = document.getElementById('addTableBtn');

addTableBtn.addEventListener('click', async () => {
  const hall = hallOfFloor(currentFloor);
  if(!hall) return;

  const spot = findFreeSpot();
  const floor = currentFloor;

  addTableBtn.disabled = true;

  let created;
  try {
    created = await api.request('venue', '/api/v1/tables', {
      method: 'POST',
      body: {
        hall_id: hall.id,
        number: Number(nextTableNumber(floor)),
        capacity: 4,
        x: clamp01(spot.x / HALL_WIDTH),
        y: clamp01(spot.y / HALL_HEIGHT)
      }
    });
  } catch (err) {
    ui.toast(err.message, 'error');

    return;
  } finally {
    addTableBtn.disabled = false;
  }

  const newTableData = tableFromApi(created);

  tablesData.push(newTableData);
  if(floor !== currentFloor) return; // пока ждали ответ, переключили этаж

  const newGroup = createTableObject(newTableData);
  canvas.add(newGroup);

  canvas.setActiveObject(newGroup);
  updateStats();
});



// Удаление столика
document.getElementById('deleteTableBtn').addEventListener('click', async () => {
  const activeObject = canvas.getActiveObject();
  if(!activeObject || !activeObject.tableData) return;

  const tableId = activeObject.tableData.id;

  // активные брони на этот столик с сегодняшнего дня (или на мероприятие без даты)
  let blocking;
  try {
    const today = toLocalDateString(new Date());
    const active = await api.request('booking', `/api/v1/bookings?table_id=${tableId}&active=true`);
    blocking = active
      .filter(b => !b.booking_date || b.booking_date >= today)
      .sort((a, b) => (a.booking_date || '').localeCompare(b.booking_date || ''));
  } catch (err) {
    ui.toast(err.message, 'error');

    return;
  }

  if(blocking.length) {
    // какие брони мешают: "31 декабря 22:00 - Алексей"
    const describe = (b) => {
      const when = b.booking_date ? formatDateHuman(b.booking_date) : 'дата мероприятия';
      const time = b.starts_at ? ` ${toLocalTime(b.starts_at)}` : '';

      return `${when}${time} - ${b.guest_name || 'гость из приложения'}`;
    };

    const shown = blocking.slice(0, 5).map(describe).join('; ');
    const more = blocking.length > 5 ? ` и ещё ${blocking.length - 5}` : '';

    const showBookings = await ui.confirm({
      title: `На стол №${activeObject.tableData.number} есть брони`,
      message: `Удалить стол можно после отмены броней: ${shown}${more}.`,
      okText: 'Показать брони',
      cancelText: 'Закрыть'
    });

    // переходим к списку броней на дату ближайшей
    const firstDate = blocking.find(b => b.booking_date)?.booking_date;
    if(showBookings && firstDate) {
      dateFilter.value = firstDate;
      showReservationsView();
      await onDateChange();
    }

    return;
  }

  const ok = await ui.confirm({
    title: `Удалить стол №${activeObject.tableData.number}?`,
    message: 'Стол пропадёт со схемы. Отменить это действие нельзя.',
    okText: 'Удалить',
    danger: true
  });

  if(!ok) return;

  try {
    await api.request('venue', `/api/v1/tables/${tableId}`, { method: 'DELETE' });
  } catch (err) {
    ui.toast(err.message, 'error');

    return;
  }

  tablesData = tablesData.filter(t => t.id !== tableId);
  dirtyLayout.delete(tableId);
  canvas.remove(activeObject);
  canvas.discardActiveObject();

  canvas.renderAll();
  updateStats();

  ui.toast('Стол удалён', 'success');
});



// Проверка вместимости столика при изменении количества гостей в форме бронирования
const modalGuestsCount = document.getElementById('modalGuestsCount');
const capacityWarning = document.getElementById('capacityWarning');

function checkTableCapacity() {
  const selectedTableId = modalTableSelect.value;
  const guests = Number(modalGuestsCount.value) || 0;

  const table = tablesData.find(t => t.id === selectedTableId);
  if(table && guests > table.capacity) {
    capacityWarning.classList.remove('hidden');
  } else {
    capacityWarning.classList.add('hidden');
  }
}

modalGuestsCount.addEventListener('input', checkTableCapacity);

// телефон гостя: только цифры, пробелы ставятся сами
document.getElementById('modalGuestPhone').addEventListener('input', (e) => {
  e.target.value = formatLocalPhone(e.target.value);
});
document.getElementById('modalTableSelect').addEventListener('change', checkTableCapacity);



// Перетаскивание объекта
canvas.on('object:moving', (options) => {
  const target = options.target;
  if (!target.tableData) return;

  const canvasWidth = HALL_WIDTH;
  const canvasHeight = HALL_HEIGHT;
  const SNAP_THRESHOLD = 15;

  // 1. Сначала ограничиваем движение пределами канваса
  target.setCoords();
  let targetRect = target.getBoundingRect(true);

  if (targetRect.left < 0) {
    target.left += -targetRect.left;
  }
  if (targetRect.top < 0) {
    target.top += -targetRect.top;
  }
  if (targetRect.left + targetRect.width > canvasWidth) {
    target.left -= (targetRect.left + targetRect.width - canvasWidth);
  }
  if (targetRect.top + targetRect.height > canvasHeight) {
    target.top -= (targetRect.top + targetRect.height - canvasHeight);
  }

  target.setCoords();
  targetRect = target.getBoundingRect(true);

  // 2. Расчет прилипания к соседним столикам
  canvas.getObjects().forEach((obj) => {
    if (obj === target || !obj.tableData) return;

    const objRect = obj.getBoundingRect(true);

    const isNearbyY = Math.abs(targetRect.top - objRect.top) < objRect.height + SNAP_THRESHOLD;
    const isNearbyX = Math.abs(targetRect.left - objRect.left) < objRect.width + SNAP_THRESHOLD;

    if (isNearbyY) {
      // Прилипание справа
      if (Math.abs(targetRect.left - (objRect.left + objRect.width)) < SNAP_THRESHOLD) {
        target.left = objRect.left + objRect.width + (target.left - targetRect.left);
      }
      // Прилипание слева
      else if (Math.abs((targetRect.left + targetRect.width) - objRect.left) < SNAP_THRESHOLD) {
        target.left = objRect.left - targetRect.width + (target.left - targetRect.left);
      }
      // Выравнивание по верхнему краю
      else if (Math.abs(targetRect.left - objRect.left) < SNAP_THRESHOLD) {
        target.left = objRect.left + (target.left - targetRect.left);
      }
    }

    if (isNearbyX) {
      // Прилипание снизу
      if (Math.abs(targetRect.top - (objRect.top + objRect.height)) < SNAP_THRESHOLD) {
        target.top = objRect.top + objRect.height + (target.top - targetRect.top);
      }
      // Прилипание сверху
      else if (Math.abs((targetRect.top + targetRect.height) - objRect.top) < SNAP_THRESHOLD) {
        target.top = objRect.top - targetRect.height + (target.top - targetRect.top);
      }
      // Выравнивание по левому краю
      else if (Math.abs(targetRect.top - objRect.top) < SNAP_THRESHOLD) {
        target.top = objRect.top + (target.top - targetRect.top);
      }
    }
  });

  target.setCoords();
  syncTableData(target);
  canvas.renderAll();
});



// Масштабирование объекта
canvas.on('object:scaling', (options) => {
  const target = options.target;
  if (!target.tableData) return;

  // Предотвращаем выворачивание наизнанку (отрицательные масштабы)
  if (target.scaleX < 0.3) target.scaleX = 0.3;
  if (target.scaleY < 0.3) target.scaleY = 0.3;

  const canvasWidth = HALL_WIDTH;
  const canvasHeight = HALL_HEIGHT;

  target.setCoords();
  const rect = target.getBoundingRect(true);

  // Ограничение выхода за границы при масштабировании
  if (rect.left < 0) target.left -= rect.left;
  if (rect.top < 0) target.top -= rect.top;
  if (rect.left + rect.width > canvasWidth) {
    target.left -= (rect.left + rect.width - canvasWidth);
  }
  if (rect.top + rect.height > canvasHeight) {
    target.top -= (rect.top + rect.height - canvasHeight);
  }

  target.setCoords();
  syncTableData(target);
  canvas.renderAll();
});



// Синхронизация данных объекта с временной БД
function syncTableData(target) {
  if (!target || !target.tableData) return;

  target.tableData.x = target.left;
  target.tableData.y = target.top;
  target.tableData.scaleX = target.scaleX;
  target.tableData.scaleY = target.scaleY;

  const found = tablesData.find(t => t.id === target.tableData.id);
  if (found) {
    const moved = found.x !== target.left || found.y !== target.top
      || found.scaleX !== target.scaleX || found.scaleY !== target.scaleY;

    found.x = target.left;
    found.y = target.top;
    found.scaleX = target.scaleX;
    found.scaleY = target.scaleY;

    if(moved) dirtyLayout.add(found.id);
  }
}



// Сбрасываем временные сохраненные данные после завершения масштабирования
canvas.on('mouse:up', () => {
  canvas.getObjects().forEach(obj => {
    delete obj.__lastValid;
  });
});



// Сохранение схемы (Синхронизация позиции и масштаба)
canvas.on('object:modified', (e) => {
  if (e.target) syncTableData(e.target);
});



// Сохранение схемы (отправка бэкенду)
const saveLayoutBtn = document.getElementById('saveLayoutBtn');

saveLayoutBtn.addEventListener('click', async () => {
  canvas.getObjects().forEach(obj => syncTableData(obj));

  if(dirtyLayout.size === 0) {
    ui.toast('Схема уже сохранена', 'info');

    return;
  }

  saveLayoutBtn.disabled = true;

  const ids = [...dirtyLayout];
  const results = await Promise.allSettled(ids.map(id => {
    const table = tablesData.find(t => t.id === id);

    return api.request('venue', `/api/v1/tables/${id}`, { method: 'PATCH', body: layoutToApi(table) });
  }));

  saveLayoutBtn.disabled = false;

  const failed = results.filter(r => r.status === 'rejected');
  ids.forEach((id, i) => { if(results[i].status === 'fulfilled') dirtyLayout.delete(id); });

  if(failed.length) ui.toast(`Не удалось сохранить ${failed.length} из ${ids.length}: ${failed[0].reason.message}`, 'error');
  else ui.toast('Схема сохранена', 'success');
});

// Предупреждение при уходе со страницы с несохранённой схемой
window.addEventListener('beforeunload', (e) => {
  if(dirtyLayout.size === 0) return;

  e.preventDefault();
  e.returnValue = '';
});



// Рендер таблицы броней
function renderReservations() {
  const selectedDate = dateFilter.value;
  const tbody = document.getElementById('reservationsTableBody');
  tbody.innerHTML = '';

  document.getElementById('printTitle').textContent = `Брони на ${formatDateHuman(selectedDate)}`;

  const query = reservationSearch.value.trim().toLowerCase();

  const filtered = reservationsData
    .filter(r => r.date === selectedDate && matchesSearch(r, query))
    .sort((a, b) => a.time.localeCompare(b.time));

  if(filtered.length === 0) {
    const emptyText = query ? 'Ничего не найдено' : `На ${formatDateHuman(selectedDate)} броней нет`;
    tbody.innerHTML = `<tr><td colspan="9" class="empty-row">${emptyText}</td></tr>`;

    return;
  }

  filtered.forEach(res => {
    const table = tablesData.find(t => t.id === res.tableId); // поиск забронированного столика, чтобы узнать его номер и этаж
    const tableInfo = table
      ? `Стол №${table.number} (${table.floor} эт.)`
      : res.tableNumber ? `Стол №${res.tableNumber} (удалён)` : 'Удален';

    const tr = document.createElement('tr');
    tr.style.cursor = 'pointer';

    tr.addEventListener('click', (e) => {
      if (e.target.closest('button')) return; // при нажатии отмены (в т.ч. на её иконку) редактирование не вызываем
      openEditModal(res.id);
    });

    const eventInfo = res.eventTitle ? `<br><small style="color:var(--text-muted)">🎉 ${escapeHtml(res.eventTitle)}</small>` : '';

    tr.innerHTML = `
      <td data-label="Время"><strong>${res.time}</strong>${eventInfo}</td>
      <td data-label="Стол">${tableInfo}</td>
      <td data-label="Гость">${escapeHtml(res.guestName)} <br><small style="color:var(--text-muted)">${escapeHtml(res.guestPhone)}</small>${res.comment ? `<br><small class="reservation-comment" title="${escapeHtml(res.comment)}">💬 ${escapeHtml(res.comment)}</small>` : ''}</td>
      <td data-label="Гостей">${res.guestsCount} чел</td>
      <td data-label="Сумма">${res.totalAmount || 0} сом</td>
      <td data-label="Предоплата">${res.prepayment} сом</td>
      <td data-label="Оплата">
        <span class="badge ${res.paymentStatus === 'paid' ? 'badge-success' : 'badge-warning'}">
          ${res.paymentStatus === 'paid' ? 'Предоплата внесена' : 'Оплата на месте'}
        </span>
      </td>
      <td data-label="Статус">
        <span class="badge ${res.apiStatus === 'CONFIRMED' ? 'badge-success' : res.status === 'active' ? 'badge-warning' : 'badge-danger'}">
          ${BOOKING_STATUS_LABELS[res.apiStatus]}
        </span>
      </td>
      <td class="cell-actions">
        ${res.status === 'active' ? 
          `<button class="btn btn-outline-danger btn-sm" onclick="cancelReservation('${res.id}')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg>Отменить</button>` : 
          `<small title="${escapeHtml(res.cancelReason)}">${escapeHtml(res.cancelReason || BOOKING_STATUS_LABELS[res.apiStatus])}</small>`
        }
      </td>
    `;

    tbody.appendChild(tr);
  });
}



// Поиск по имени, телефону (по цифрам) или номеру стола
function matchesSearch(res, query) {
  if(!query) return true;

  const digits = query.replace(/\D/g, '');
  const table = tablesData.find(t => t.id === res.tableId);

  return res.guestName.toLowerCase().includes(query)
    || (digits.length > 0 && res.guestPhone.replace(/\D/g, '').includes(digits))
    || String(table ? table.number : res.tableNumber) === query.replace('№', '').trim();
}

reservationSearch.addEventListener('input', renderReservations);



// Открытие модального окна редактирования брони
function openEditModal(resId) {
  const res = reservationsData.find(r => r.id === resId);
  if(!res) return;

  if(res.status !== 'active') {
    ui.toast('Отменённую или истёкшую бронь изменить нельзя', 'warning');

    return;
  }

  const table = tablesData.find(t => t.id === res.tableId);

  document.getElementById('modalTitle').textContent = 'Редактирование брони';
  document.getElementById('modalReservationId').value = res.id;

  modalFloorSelect.value = table ? table.floor : 1;
  modalDate.value = res.date;
  modalReservations = null;

  fillEventSelect(res.eventId);
  updateAvailableTablesInModal(res.tableId); // обновляем доступные столики с учетом редактируемого
  modalTableSelect.value = res.tableId; // устанавливаем столик после обновления списка option

  document.getElementById('modalTime').value = res.time;
  document.getElementById('modalGuestName').value = res.guestName;
  document.getElementById('modalGuestPhone').value = phoneToLocal(res.guestPhone);
  document.getElementById('modalGuestsCount').value = res.guestsCount;
  document.getElementById('modalTotalAmount').value = res.totalAmount || 0;
  document.getElementById('modalPrepayment').value = res.prepayment;
  document.getElementById('modalPaymentStatus').value = res.paymentStatus;
  showModalComment(res.comment);
  document.getElementById('submitReservationBtn').textContent = 'Сохранить изменения';
  cancelBookingBtn.classList.remove('hidden');

  checkTableCapacity();
  reservationModal.classList.remove('hidden');
}



// Отмена брони с указанием причины
window.cancelReservation = async function(resId) {
  const res = reservationsData.find(r => r.id === resId);
  if(!res) return;

  const reason = await ui.prompt({
    title: 'Отменить бронь?',
    message: `${res.guestName}, ${res.time}. Укажите причину отмены:`,
    options: ['Гость отменил', 'Гость не пришёл', 'Ошибка при записи'],
    placeholder: 'Своя причина',
    okText: 'Отменить бронь',
    cancelText: 'Не отменять',
    danger: true
  });

  if(reason === null) return; // нажата "не отменять"

  try {
    await api.request('booking', `/api/v1/bookings/${resId}/cancel`, {
      method: 'POST',
      body: { reason: reason || 'Без указания причины' }
    });
  } catch (err) {
    ui.toast(err.message, 'error');

    return;
  }

  // статус столика пересчитывается по броням на выбранную дату (Недоступен / Занят не трогаем)
  await loadReservations();
  renderReservations();
  updateCanvasColorsByDate();

  ui.toast('Бронь отменена', 'success');
};



// Динамическая визуальная бронь только на выбранную дату
function updateCanvasColorsByDate() {
  const selectedDate = dateFilter.value;

  canvas.getObjects().forEach(obj => {
    if(!obj.tableData) return;
    if(obj.tableData.status === 'occupied' || obj.tableData.status === 'disabled') return;

    // есть ли активная бронь столика на дату
    const hasBooking = reservationsData.some(r => 
    r.tableId === obj.tableData.id && r.date === selectedDate && r.status === 'active');

    if(hasBooking) obj.tableData.status = 'booked';
    else obj.tableData.status = 'free';

    // Синхронизация с массивом
    const foundInDB = tablesData.find(t => t.id === obj.tableData.id);
    if(foundInDB) foundInDB.status = obj.tableData.status;

    // Красим столик
    const rect = obj.item(0);
    rect.set('fill', getStatusColor(obj.tableData.status));
  });

  canvas.renderAll();
  updateStats();
  refreshTableBookingInfo();
}

async function onDateChange() {
  await loadReservations();
  renderReservations();
  updateCanvasColorsByDate();
}

dateFilter.addEventListener('change', onDateChange);


// Стрелки дня и "Сегодня"
function shiftDate(days) {
  const date = new Date((dateFilter.value || toLocalDateString(new Date())) + 'T00:00');
  date.setDate(date.getDate() + days);

  dateFilter.value = toLocalDateString(date);
  onDateChange();
}

document.getElementById('prevDayBtn').addEventListener('click', () => shiftDate(-1));
document.getElementById('nextDayBtn').addEventListener('click', () => shiftDate(1));
document.getElementById('todayBtn').addEventListener('click', () => {
  dateFilter.value = toLocalDateString(new Date());
  onDateChange();
});



// Окно бронирования
const reservationModal = document.getElementById('reservationModal');
const openModalBtn = document.getElementById('openReservationModalBtn');
const closeModalBtn = document.getElementById('closeModalBtn');
const cancelModalBtn = document.getElementById('cancelModalBtn');
const createForm = document.getElementById('createReservationForm');

const modalFloorSelect = document.getElementById('modalFloorSelect');
const modalTableSelect = document.getElementById('modalTableSelect');
const modalDate = document.getElementById('modalDate');


// Комментарий оставляет гость в приложении, в админке он только для чтения
function showModalComment(comment) {
  document.getElementById('modalCommentText').textContent = comment;
  document.getElementById('modalComment').classList.toggle('hidden', !comment);
}


function openNewReservationModal(table = null) {
  document.getElementById('modalTitle').textContent = table ? `Бронь стола №${table.number}` : 'Новое бронирование';
  document.getElementById('modalReservationId').value = '';
  document.getElementById('submitReservationBtn').textContent = 'Забронировать';
  cancelBookingBtn.classList.add('hidden');

  createForm.reset(); // сброс формы, чтобы не было старых данных
  showModalComment('');

  modalDate.value = dateFilter.value;
  modalFloorSelect.value = table ? table.floor : currentFloor;
  modalReservations = null;

  // если в этот день мероприятие - по умолчанию бронь на него
  const dayEvents = fillEventSelect();
  if(dayEvents.length === 1) {
    modalEventSelect.value = dayEvents[0].id;
    document.getElementById('modalTime').value = toLocalTime(dayEvents[0].starts_at);
  }

  updateAvailableTablesInModal();
  if(table) modalTableSelect.value = table.id;

  checkTableCapacity();
  reservationModal.classList.remove('hidden');
  document.getElementById('modalGuestName').focus();
}

openModalBtn.addEventListener('click', () => openNewReservationModal());


function closeModal() {
  reservationModal.classList.add('hidden');

  createForm.reset();
}

closeModalBtn.addEventListener('click', closeModal);
cancelModalBtn.addEventListener('click', closeModal);

// Отмена брони прямо из окна (например, открытой со схемы)
const cancelBookingBtn = document.getElementById('cancelBookingBtn');

cancelBookingBtn.addEventListener('click', () => {
  const resId = document.getElementById('modalReservationId').value;

  closeModal();
  cancelReservation(resId);
});


const modalEventSelect = document.getElementById('modalEventSelect');

// Мероприятия на дату из окна брони (отменённые не предлагаем)
function fillEventSelect(selectedId = null) {
  const dayEvents = eventsOnDate(modalDate.value)
    .filter(ev => ev.status !== 'CANCELLED' || ev.id === selectedId);

  modalEventSelect.innerHTML = '<option value="">Без мероприятия</option>';

  dayEvents.forEach(ev => {
    const opt = document.createElement('option');
    opt.value = ev.id;
    opt.textContent = `${toLocalTime(ev.starts_at)} ${ev.title}${ev.status === 'DRAFT' ? ' (черновик)' : ''}`;

    modalEventSelect.appendChild(opt);
  });

  modalEventSelect.value = selectedId ? String(selectedId) : '';

  return dayEvents;
}

// время брони по умолчанию - начало мероприятия
modalEventSelect.addEventListener('change', () => {
  const event = eventsData.find(ev => String(ev.id) === modalEventSelect.value);
  if(event) document.getElementById('modalTime').value = toLocalTime(event.starts_at);

  updateAvailableTablesInModal(currentModalTableId());
});

// столик редактируемой брони остаётся в списке доступных
function currentModalTableId() {
  const resId = document.getElementById('modalReservationId').value;
  const res = reservationsData.find(r => r.id === resId);

  return res ? res.tableId : null;
}

// Другая дата в окне брони - загружаем брони на неё для списка свободных столов
async function onModalDateChange() {
  const date = modalDate.value;

  fillEventSelect();
  modalReservations = date === dateFilter.value ? null : [];
  updateAvailableTablesInModal(currentModalTableId());

  if(date === dateFilter.value || !date) return;

  try {
    const items = await fetchReservations(date);
    if(modalDate.value !== date) return;

    modalReservations = items;
    updateAvailableTablesInModal(currentModalTableId());
  } catch (err) {
    ui.toast(`Брони на ${formatDateHuman(date)} не загрузились: ${err.message}`, 'warning');
  }
}

// Пересчет доступных столов при изменении этажа или даты (с учетом редактируемого столика)
modalFloorSelect.addEventListener('change', () => updateAvailableTablesInModal(currentModalTableId()));
modalDate.addEventListener('change', onModalDateChange);

function updateAvailableTablesInModal(currentTableId = null) {
  const selectedFloor = Number(modalFloorSelect.value);
  const selectedDate = modalDate.value;

  modalTableSelect.innerHTML = '';

  const floorTables = tablesData.filter(t => t.floor === selectedFloor); // все столики текущего этажа

  const dayReservations = modalReservations || reservationsData;
  const eventId = modalEventSelect.value ? Number(modalEventSelect.value) : null;

  // Находим только столики без активной брони на выбранную дату
  const availableTalbes = floorTables.filter(table => {
    // недоступный стол бронировать нельзя (кроме уже забронированного в редактируемой брони)
    if(table.status === 'disabled' && table.id !== currentTableId) return false;

    // Стол доступен, если на него нет активной брони либо это редактируемый столик
    const hasBooking = dayReservations.some(r =>
      r.tableId === table.id && r.date === selectedDate && r.status === 'active' && r.id !== document.getElementById('modalReservationId').value
      && (eventId === null || r.eventId === null || r.eventId === eventId)
    );

    return !hasBooking;
  });

  if(availableTalbes.length === 0) {
    modalTableSelect.innerHTML = `<option value="">Нет свободных столиков</option>`;

    return;
  }

  availableTalbes.forEach(table => {
    const opt = document.createElement('option');
    opt.value = table.id;
    opt.textContent = `Стол №${table.number} (${table.capacity} мест${table.price !== null ? `, ${formatPrice(table.price)} сом` : ''})`;

    modalTableSelect.appendChild(opt);
  });
}


// Отправка формы (создание или обновление брони)
createForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  
  const resId = document.getElementById('modalReservationId').value;

  const tableId = modalTableSelect.value;
  if(!tableId) {
    ui.toast('Выберите свободный столик', 'error');

    return;
  }


  const totalAmount = Number(document.getElementById('modalTotalAmount').value) || 0;
  const prepayment = Number(document.getElementById('modalPrepayment').value) || 0;

  if(prepayment > totalAmount && totalAmount > 0) {
    ui.toast('Предоплата не может быть больше суммы брони', 'error');

    return;
  }


  let paymentStatus = document.getElementById('modalPaymentStatus').value;
  if(totalAmount > 0 && prepayment === totalAmount) {
    paymentStatus = 'paid';
  }

  const phoneDigits = document.getElementById('modalGuestPhone').value.replace(/\D/g, '');
  if(phoneDigits.length !== 9) {
    ui.toast('Введите номер телефона: 9 цифр после +996', 'error');
    document.getElementById('modalGuestPhone').focus();

    return;
  }

  const date = modalDate.value;
  const time = document.getElementById('modalTime').value;
  if(!date || !time) {
    ui.toast('Укажите дату и время', 'error');

    return;
  }

  const payload = {
    table_id: Number(tableId),
    event_id: modalEventSelect.value ? Number(modalEventSelect.value) : null,
    starts_at: new Date(`${date}T${time}`).toISOString(),
    guests: Number(document.getElementById('modalGuestsCount').value),
    guest_name: document.getElementById('modalGuestName').value.trim(),
    guest_phone: '+996' + phoneDigits,
    total_amount: totalAmount || null,
    prepayment: prepayment || null,
    prepayment_paid: paymentStatus === 'paid'
  };

  const submitBtn = document.getElementById('submitReservationBtn');
  submitBtn.disabled = true;

  try {
    if(resId) {
      await api.request('booking', `/api/v1/bookings/${resId}`, { method: 'PATCH', body: payload });
    } else {
      await api.request('booking', '/api/v1/bookings/admin', { method: 'POST', body: payload });
    }
  } catch (err) {
    ui.toast(err.message, 'error');

    return;
  } finally {
    submitBtn.disabled = false;
  }

  closeModal();

  // бронь могли создать на другую дату - показываем её
  if(date !== dateFilter.value) dateFilter.value = date;

  await onDateChange();

  ui.toast(resId ? 'Изменения брони сохранены' : 'Бронь создана', 'success');
});



// Печать и экспорт
document.getElementById('printReservationsBtn').addEventListener('click', () => {
  window.print(); 
});

document.getElementById('exportReservationsBtn').addEventListener('click', () => {
  const selectedDate = dateFilter.value;
  const filtered = reservationsData.filter(r => r.date === selectedDate);

  if(filtered.length === 0) {
    ui.toast('На эту дату нет броней для выгрузки', 'warning');

    return;
  }

  let csvContent = "\uFEFFВремя;Стол;Гость;Телефон;Гостей;Предоплата;Статус\n";
  filtered.forEach(r => {
    const table = tablesData.find(t => t.id === r.tableId);
    const tableNum = table ? table.number : r.tableNumber ?? '-';

    csvContent += `${r.time};Стол №${tableNum};${r.guestName};${r.guestPhone};${r.guestsCount};${r.prepayment};${r.status}\n`;
  });

  // Скачивание файла
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.setAttribute("href", url);
  link.setAttribute("download", `reservations_${selectedDate}.csv`);

  document.body.appendChild(link);
  link.click();

  document.body.removeChild(link);
});



// Старт: загружаем залы и столы, восстанавливаем этаж и вкладку с прошлого раза
async function init() {
  fitCanvasToWrapper();

  const hint = noSelectionText.innerHTML;
  noSelectionText.textContent = 'Загрузка схемы зала...';

  try {
    await loadHalls();
    await loadTables();
    noSelectionText.innerHTML = hint;

    // без мероприятий брони на обычные вечера всё равно работают
    await loadEvents().catch(err => ui.toast(`Мероприятия не загрузились: ${err.message}`, 'warning'));
    await loadReservations();
  } catch (err) {
    noSelectionText.textContent = `Не удалось загрузить схему зала: ${err.message}`;
    ui.toast(err.message, 'error');
    addTableBtn.disabled = true;
    saveLayoutBtn.disabled = true;
  }

  setFloor(loadPreference('hallFloor') === '2' ? 2 : 1);

  if(loadPreference('hallView') === 'reservations') showReservationsView();
}

init();