// Инициализация Canvas
const canvas = new fabric.Canvas('hallCanvas', {
  backgroundColor: 'transparent',
  selection: false // запрет выделения нескольких объектов
});

const wrapper = document.querySelector('.canvas-wrapper');
canvas.setWidth(wrapper.clientWidth);
canvas.setHeight(wrapper.clientHeight);


// глобальный запрет выворачивания столиков наизнанку
fabric.Object.prototype.lockScalingFlip = true;
fabric.Object.prototype.noScaleResetX = true;


let currentFloor = 1;


// временная БД столиков
let tablesData = [
  { id: 't1', floor: 1, number: '1', capacity: 4, status: 'free', x: 100, y: 100 },
  { id: 't2', floor: 1, number: '2', capacity: 2, status: 'booked', x: 300, y: 100 },
  { id: 't3', floor: 2, number: '201', capacity: 6, status: 'free', x: 150, y: 150 }
];

// временная БД бронирований
let reservationsData = [
  {
    id: 'res_1',
    tableId: 't2',
    date: new Date().toISOString().split('T')[0], // установлено на сегодня с приколами ISO-формата
    time: '19:00',
    guestName: 'Алексей',
    guestPhone: '+996 555 123456',
    guestsCount: 4,
    totalAmount: 5000,
    prepayment: 1000,
    paymentStatus: 'paid',
    status: 'active',
    cancelReason: ''
  }
];


// Общий DOM
const noSelectionText = document.getElementById('noSelectionText');
const tablePropsForm = document.getElementById('tablePropsForm');
const propNumber = document.getElementById('propNumber');
const propCapacity = document.getElementById('propCapacity');
const propStatus = document.getElementById('propStatus');

const viewCanvasBtn = document.getElementById('viewCanvasBtn');
const viewReservationsBtn = document.getElementById('viewReservationsBtn');

const canvasHeaderControls = document.getElementById('canvasHeaderControls');
const canvasView = document.getElementById('canvasView');
const reservationsSection = document.getElementById('reservationsSection');

const dateFilter = document.getElementById('reservationDateFilter');
dateFilter.value = new Date().toISOString().split('T')[0]; // ISO формат даты (Г-М-Д) и первая часть из формата (дата)



// Переключение вкладок и этажей
viewCanvasBtn.addEventListener('click', () => {
  viewCanvasBtn.classList.add('active');
  viewReservationsBtn.classList.remove('active');

  canvasHeaderControls.classList.remove('hidden');
  canvasView.classList.remove('hidden');
  reservationsSection.classList.add('hidden');

  renderFloor(currentFloor);
});

viewReservationsBtn.addEventListener('click', () => {
  viewReservationsBtn.classList.add('active');
  viewCanvasBtn.classList.remove('active');

  canvasHeaderControls.classList.add('hidden');
  canvasView.classList.add('hidden');
  reservationsSection.classList.remove('hidden');

  renderReservations(); // обновляем таблицу при открытии вкладки
});



// Переключение этажей
const floor1Btn = document.getElementById('floor1Btn');
const floor2Btn = document.getElementById('floor2Btn');

floor1Btn.addEventListener('click', () => {
  currentFloor = 1;

  floor1Btn.classList.add('active');
  floor2Btn.classList.remove('active');

  renderFloor(1);
});

floor2Btn.addEventListener('click', () => {
  currentFloor = 2;

  floor2Btn.classList.add('active');
  floor1Btn.classList.remove('active');
  
  renderFloor(2);
});



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

  const freeCount = currentTables.filter(t => t.status === 'free').length;
  const bookedCount = currentTables.filter(t => t.status !== 'free').length;

  document.getElementById('statFreeCount').textContent = freeCount;
  document.getElementById('statBookedCount').textContent = bookedCount;
  document.getElementById('statTotalSeats').textContent = currentTables.length;
}



// Выделение столиков и отображение свойств в боковой панели
canvas.on('selection:created', handleSelection);
canvas.on('selection:updated', handleSelection);

canvas.on('selection:cleared', () => {
  tablePropsForm.classList.add('hidden');
  noSelectionText.classList.remove('hidden');
});

function handleSelection(e) {
  const selectedObject = e.selected[0];

  // выбран ли столик
  if(selectedObject && selectedObject.tableData) {
    const data = selectedObject.tableData;

    propNumber.value = data.number;
    propCapacity.value = data.capacity;
    propStatus.value = data.status;

    noSelectionText.classList.add('hidden');
    tablePropsForm.classList.remove('hidden');
  }
}



// Изменение свойств столика в боковой панели
function updateActiveTable() {
  const activeObject = canvas.getActiveObject();
  if(!activeObject || !activeObject.tableData) return;

  const selectedDate = dateFilter.value;
  const hasActiveBooking = reservationsData.some(r =>
    r.tableId === activeObject.tableData.id && r.date === selectedDate && r.status === 'active'
  );


  // проверяем изменение статуса
  if(propStatus.value !== activeObject.tableData.status) {
    if(propStatus.value === 'booked' && !hasActiveBooking) {
      alert('Нельзя установить данный статус без активной брони!');
      propStatus.value = activeObject.tableData.status; // возвращаем прежний статус
    }

    if (hasActiveBooking && (propStatus.value === 'free' || propStatus.value === 'disabled')) {
      alert('Этот стол забронирован! Отмените или отредактируйте бронь в списке броней.');
      propStatus.value = 'booked';
  
      return;
    }
  }


  activeObject.tableData.number = propNumber.value;
  activeObject.tableData.capacity = propCapacity.value;
  activeObject.tableData.status = propStatus.value;

  const found = tablesData.find(t => t.id === activeObject.tableData.id);
  if(found) {
    found.number = propNumber.value;
    found.capacity = propCapacity.value;
    found.status = propStatus.value;
  }

  // обновляем визуал (цвет и текст внутри группы)
  const rect = activeObject.item(0);
  const text = activeObject.item(1);

  rect.set('fill', getStatusColor(propStatus.value));
  text.set('text', `№${propNumber.value}\n(${propCapacity.value} чел)`);

  canvas.renderAll(); // перерисовка Canvas
  updateStats();
}

propNumber.addEventListener('input', updateActiveTable);
propCapacity.addEventListener('input', updateActiveTable);
propStatus.addEventListener('change', updateActiveTable);



// Добавление столика
document.getElementById('addTableBtn').addEventListener('click', () => {
  const newTableData = {
    id: 't_' + Date.now(),
    floor: currentFloor,
    number: String(tablesData.length + 1),
    capacity: 4,
    status: 'free',

    x: 200,
    y: 200,

    scaleX: 1,
    scaleY: 1
  };

  tablesData.push(newTableData);
  const newGroup = createTableObject(newTableData);
  canvas.add(newGroup);

  canvas.setActiveObject(newGroup);
  updateStats();
});



// Удаление столика
document.getElementById('deleteTableBtn').addEventListener('click', () => {
  const activeObject = canvas.getActiveObject();
  if(!activeObject || !activeObject.tableData) return;

  const tableId = activeObject.tableData.id;
  // есть ли активная бронь на этот столик
  const hasBookings = reservationsData.some(r => r.tableId === tableId && r.status === 'active');
  if(hasBookings) {
    alert('Нельзя удалить столик, на который есть активные бронирования! Сначала отмените брони.');

    return;
  }

  if(!confirm(`Вы уверены, что хотите удалить столик №${activeObject.tableData.number}?`)) return;

  // удаление (из локального массива)
  tablesData = tablesData.filter(t => t.id !== tableId);
  canvas.remove(activeObject);
  canvas.discardActiveObject();

  canvas.renderAll();
  updateStats();
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



// Перетаскивание объекта
canvas.on('object:moving', (options) => {
  const target = options.target;
  if (!target.tableData) return;

  const canvasWidth = canvas.getWidth();
  const canvasHeight = canvas.getHeight();
  const SNAP_THRESHOLD = 15;

  // 1. Сначала ограничиваем движение пределами канваса
  target.setCoords();
  let targetRect = target.getBoundingRect();

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
  targetRect = target.getBoundingRect();

  // 2. Расчет прилипания к соседним столикам
  canvas.getObjects().forEach((obj) => {
    if (obj === target || !obj.tableData) return;

    const objRect = obj.getBoundingRect();

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

  const canvasWidth = canvas.getWidth();
  const canvasHeight = canvas.getHeight();

  target.setCoords();
  const rect = target.getBoundingRect();

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
    found.x = target.left;
    found.y = target.top;
    found.scaleX = target.scaleX;
    found.scaleY = target.scaleY;
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
document.getElementById('saveLayoutBtn').addEventListener('click', () => {
  canvas.getObjects().forEach(obj => syncTableData(obj));
  alert('Схема успешно сохранена!');
});



// Рендер таблицы броней
function renderReservations() {
  const selectedDate = dateFilter.value;
  const tbody = document.getElementById('reservationsTableBody');
  tbody.innerHTML = '';

  const filtered = reservationsData.filter(r => r.date === selectedDate);
  if(filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color: var(--text-muted);">На выбранную дату броней нет</td></tr>`;

    return;
  }

  filtered.forEach(res => {
    const table = tablesData.find(t => t.id === res.tableId); // поиск забронированного столика, чтобы узнать его номер и этаж
    const tableInfo = table ? `Стол №${table.number} (${table.floor} эт.)` : 'Удален';

    const tr = document.createElement('tr');
    tr.style.cursor = 'pointer';

    tr.addEventListener('click', (e) => {
      if (e.target.tagName === 'BUTTON') return; // при нажатии отмены редактирование не вызываем
      openEditModal(res.id);
    });

    tr.innerHTML = `
      <td><strong>${res.time}</strong></td>
      <td>${tableInfo}</td>
      <td>${res.guestName} <br><small style="color:var(--text-muted)">${res.guestPhone}</small></td>
      <td>${res.guestsCount} чел</td>
      <td>${res.totalAmount || 0} сом</td>
      <td>${res.prepayment} сом</td>
      <td>
        <span class="badge ${res.paymentStatus === 'paid' ? 'badge-success' : 'badge-warning'}">
          ${res.paymentStatus === 'paid' ? 'Оплачено' : 'При входе'}
        </span>
      </td>
      <td>
        <span class="badge ${res.status === 'active' ? 'badge-success' : 'badge-danger'}">
          ${res.status === 'active' ? 'Активна' : 'Отменена'}
        </span>
      </td>
      <td>
        ${res.status === 'active' ? 
          `<button class="btn btn-danger" style="padding:4px 8px; font-size:0.75rem;" onclick="cancelReservation('${res.id}')">Отменить</button>` : 
          `<small title="${res.cancelReason}">${res.cancelReason || 'Отменено'}</small>`
        }
      </td>
    `;

    tbody.appendChild(tr);
  });
}



// Открытие модального окна редактирования брони
function openEditModal(resId) {
  const res = reservationsData.find(r => r.id === resId);
  if(!res) return;

  const table = tablesData.find(t => t.id === res.tableId);

  document.getElementById('modalTitle').textContent = 'Редактирование брони';
  document.getElementById('modalReservationId').value = res.id;

  modalFloorSelect.value = table ? table.floor : 1;
  modalDate.value = res.date;

  updateAvailableTablesInModal(res.tableId); // обновляем доступные столики с учетом редактируемого
  modalTableSelect.value = res.tableId; // устанавливаем столик после обновления списка option

  document.getElementById('modalTime').value = res.time;
  document.getElementById('modalGuestName').value = res.guestName;
  document.getElementById('modalGuestPhone').value = res.guestPhone;
  document.getElementById('modalGuestsCount').value = res.guestsCount;
  document.getElementById('modalTotalAmount').value = res.totalAmount || 0;
  document.getElementById('modalPrepayment').value = res.prepayment;
  document.getElementById('modalPaymentStatus').value = res.paymentStatus;

  reservationModal.classList.remove('hidden');
}



// Отмена брони с указанием причины
window.cancelReservation = function(resId) {
  const reason = prompt('Укажите причину отмены бронирования:');
  if(reason === null) return; // нажата "отмена"

  const res = reservationsData.find(r => r.id === resId);
  if(res) {
    res.status = 'cancelled';
    res.cancelReason = reason || 'Без указания причины';

    const table = tablesData.find(t => t.id === res.tableId);
    if(table) table.status = 'free';

    // автоматическое освобождение статуса "Забронировано", если бронь была на текущую дату
    renderReservations();
    updateCanvasColorsByDate();
  }
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
}

dateFilter.addEventListener('change', () => {
  renderReservations();
  updateCanvasColorsByDate();
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


openModalBtn.addEventListener('click', () => {
  document.getElementById('modalTitle').textContent = 'Новое бронирование';
  document.getElementById('modalReservationId').value = '';

  createForm.reset(); // сброс формы, чтобы не было старых данных

  modalDate.value = dateFilter.value;

  updateAvailableTablesInModal();
  reservationModal.classList.remove('hidden');
});


function closeModal() {
  reservationModal.classList.add('hidden');

  createForm.reset();
}

closeModalBtn.addEventListener('click', closeModal);
cancelModalBtn.addEventListener('click', closeModal);


// Пересчет доступных столов при изменении этажа или даты (с учетом редактируемого столика)
modalFloorSelect.addEventListener('change', updateAvailableTablesInModal);
modalDate.addEventListener('change', updateAvailableTablesInModal);

function updateAvailableTablesInModal(currentTableId = null) {
  const selectedFloor = Number(modalFloorSelect.value);
  const selectedDate = modalDate.value;

  modalTableSelect.innerHTML = '';

  const floorTables = tablesData.filter(t => t.floor === selectedFloor); // все столики текущего этажа

  // Находим только столики без активной брони на выбранную дату
  const availableTalbes = floorTables.filter(table => {
    // Стол доступен, если на него нет активной брони либо это редактируемый столик
    const hasBooking = reservationsData.some(r =>
      r.tableId === table.id && r.date === selectedDate && r.status === 'active' && r.id !== document.getElementById('modalReservationId').value
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
    opt.textContent = `Стол №${table.number} (${table.capacity} мест)`;

    modalTableSelect.appendChild(opt);
  });
}


// Отправка формы (создание или обновление брони)
createForm.addEventListener('submit', (e) => {
  e.preventDefault();
  
  const resId = document.getElementById('modalReservationId').value;

  const tableId = modalTableSelect.value;
  if(!tableId) {
    alert('Выберите свободный столик!');

    return;
  }


  const totalAmount = Number(document.getElementById('modalTotalAmount').value) || 0;
  const prepayment = Number(document.getElementById('modalPrepayment').value) || 0;

  if(prepayment > totalAmount && totalAmount > 0) {
    alert('Предоплата не может превышать общую сумму бронирования!');

    return;
  }


  let paymentStatus = document.getElementById('modalPaymentStatus').value;
  if(totalAmount > 0 && prepayment === totalAmount) {
    paymentStatus = 'paid';
  }


  if(resId) {
    // редактирование существующей брони
    const res = reservationsData.find(r => r.id === resId);

    if(res) {
      res.tableId = tableId;
      res.date = modalDate.value;
      res.time = document.getElementById('modalTime').value;
      res.guestName = document.getElementById('modalGuestName').value;
      res.guestPhone = document.getElementById('modalGuestPhone').value;
      res.guestsCount = Number(document.getElementById('modalGuestsCount').value);
      res.totalAmount = totalAmount;
      res.prepayment = prepayment;
      res.paymentStatus = paymentStatus;
    }
  } else {
    // создание новой брони
    const newReservation = {
      id: 'res_' + Date.now(),
      tableId: tableId,
      date: modalDate.value,
      time: document.getElementById('modalTime').value,
      guestName: document.getElementById('modalGuestName').value,
      guestPhone: document.getElementById('modalGuestPhone').value,
      guestsCount: Number(document.getElementById('modalGuestsCount').value),
      totalAmount: totalAmount,
      prepayment: prepayment,
      paymentStatus: paymentStatus,
      status: 'active',
      cancelReason: ''
    };

    reservationsData.push(newReservation);
  }

  closeModal();

  renderReservations();
  updateCanvasColorsByDate();

  alert('Бронирование успешно создано!');
});



// Печать и экспорт
document.getElementById('printReservationsBtn').addEventListener('click', () => {
  window.print(); 
});

document.getElementById('exportReservationsBtn').addEventListener('click', () => {
  const selectedDate = dateFilter.value;
  const filtered = reservationsData.filter(r => r.date === selectedDate);

  if(filtered.length === 0) {
    alert('Нет данных для выгрузки');

    return;
  }

  let csvContent = "\uFEFFВремя;Стол;Гость;Телефон;Гостей;Предоплата;Статус\n";
  filtered.forEach(r => {
    const table = tablesData.find(t => t.id === r.tableId);
    const tableNum = table ? table.number : '-';

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



renderFloor(1);