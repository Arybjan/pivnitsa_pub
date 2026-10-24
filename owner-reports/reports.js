// без сессии администратора - на страницу входа
api.requireAuth();

document.addEventListener('DOMContentLoaded', () => {
  const userRole = localStorage.getItem('userRole') || 'admin';

  if(userRole !== 'owner') {
    document.querySelector('.reports-container').classList.add('hidden');
    ui.toast('Доступ запрещён: страница только для владельца', 'error');

    setTimeout(() => {
      window.location.href = '../main-menu/main.html';
    }, 1500);

    return;
  }


  const startDateInput = document.getElementById('startDate');
  const endDateInput = document.getElementById('endDate');
  const applyFilterBtn = document.getElementById('applyFilterBtn');
  const exportExcelBtn = document.getElementById('exportExcelBtn');
  const tbody = document.getElementById('reportsTableBody');


  // Г-М-Д по местному времени (toISOString сдвигает дату в UTC)
  const toLocalDateString = (date) => {
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');

    return `${date.getFullYear()}-${m}-${d}`;
  };

  // Диапазон по умолчанию (текущий месяц)
  const now = new Date();
  const firstDay = toLocalDateString(new Date(now.getFullYear(), now.getMonth(), 1));
  const lastDay = toLocalDateString(new Date(now.getFullYear(), now.getMonth() + 1, 0));

  startDateInput.value = firstDay;
  endDateInput.value = lastDay;


  // строки отчёта за последний сформированный период
  let reportRows = [];
  let reportPeriod = { start: '', end: '' };

  const STATUS_LABELS = {
    CONFIRMED: 'Успешно',
    PENDING_PAYMENT: 'Ждёт оплаты',
    CANCELLED: 'Отменено'
  };

  // экранирование текста с сервера перед вставкой в HTML
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[ch]);

  const toLocalTime = (iso) => {
    const date = new Date(iso);

    return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
  };


  // все страницы списка (limit - максимум бэкенда)
  async function fetchAll(service, path, limit, pick = (page) => page) {
    const items = [];
    let offset = 0;
    let page;

    do {
      const sep = path.includes('?') ? '&' : '?';
      page = await api.request(service, `${path}${sep}limit=${limit}&offset=${offset}`);
      items.push(...pick(page));
      offset += pick(page).length;
    } while(pick(page).length === limit);

    return items;
  }


  // Брони за период: на обычный вечер (по дате брони) + на мероприятия периода
  async function loadReport(start, end) {
    const [events, halls, tables] = await Promise.all([
      fetchAll('event', '/api/v1/events/all', 100, (page) => page.items),
      api.request('venue', '/api/v1/halls?limit=200'),
      fetchAll('venue', '/api/v1/tables', 200)
    ]);

    const eventsById = new Map(events.map(ev => [ev.id, ev]));
    const periodEventIds = events
      .filter(ev => {
        const date = toLocalDateString(new Date(ev.starts_at));

        return date >= start && date <= end;
      })
      .map(ev => ev.id);

    const requests = [fetchAll('booking', `/api/v1/bookings?date_from=${start}&date_to=${end}`, 500)];

    // id мероприятий пачками, чтобы не упереться в длину URL
    for(let i = 0; i < periodEventIds.length; i += 50) {
      const query = periodEventIds.slice(i, i + 50).map(id => `event_id=${id}`).join('&');
      requests.push(fetchAll('booking', `/api/v1/bookings?${query}`, 500));
    }

    const byId = new Map();
    (await Promise.all(requests)).flat().forEach(b => byId.set(b.id, b));

    const sortedHalls = halls.sort((a, b) => a.id - b.id);
    const tablesById = new Map(tables.map(t => [t.id, t]));

    return [...byId.values()]
      // истёкшие - неоплаченные удержания стола из приложения, бронями не стали
      .filter(b => b.status !== 'EXPIRED')
      .map(b => {
        const event = eventsById.get(b.event_id);
        const startsAt = b.starts_at || (event && event.starts_at);
        const table = tablesById.get(b.table_id);
        const floor = table ? sortedHalls.findIndex(h => h.id === table.hall_id) + 1 : 0;

        return {
          date: b.booking_date || (startsAt ? toLocalDateString(new Date(startsAt)) : ''),
          time: startsAt ? toLocalTime(startsAt) : '',
          table: table ? `Стол №${table.number}${floor ? ` (${floor} эт.)` : ''}` : b.table_number ? `Стол №${b.table_number} (удалён)` : 'Стол удалён',
          event: event ? event.title : '',
          guest: b.guest_name || 'Гость из приложения',
          count: b.guests,
          total: Number(b.total_amount) || 0,
          prepay: b.prepayment_paid ? Number(b.prepayment) || 0 : 0,
          status: b.status
        };
      })
      .filter(r => r.date >= start && r.date <= end)
      .sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time));
  }


  // фильтрация и отрисовка
  function renderReport() {
    const filtered = reportRows;

    let totalBookings = filtered.length;
    let totalPrepayment = 0;
    let totalAmount = 0;
    let canceledBookings = 0;

    tbody.innerHTML = '';

    if(filtered.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color: var(--text-muted);">За выбранный период данных нет</td></tr>`;
    }

    filtered.forEach(r => {
      // в выручку идут только подтверждённые брони
      if(r.status === 'CONFIRMED') {
        totalPrepayment += r.prepay;
        totalAmount += r.total;
      } else if(r.status === 'CANCELLED') canceledBookings++;

      const badge = { CONFIRMED: 'badge-success', PENDING_PAYMENT: 'badge-warning', CANCELLED: 'badge-danger' }[r.status];
      const eventInfo = r.event ? `<br><small style="color: var(--text-muted);">🎉 ${escapeHtml(r.event)}</small>` : '';

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td data-label="Дата">${r.date.split('-').reverse().join('.')}</td>
        <td data-label="Время">${r.time}${eventInfo}</td>
        <td data-label="Столик">${escapeHtml(r.table)}</td>
        <td data-label="Гость">${escapeHtml(r.guest)}</td>
        <td data-label="Гостей">${r.count} чел</td>
        <td data-label="Сумма">${r.total.toLocaleString()} сом</td>
        <td data-label="Предоплата">${r.prepay.toLocaleString()} сом</td>
        <td data-label="Статус">
          <span class="badge ${badge}">${STATUS_LABELS[r.status]}</span>
        </td>
      `;

      tbody.appendChild(tr);
    });

    document.getElementById('kpiTotalBookings').textContent = totalBookings;
    document.getElementById('kpiTotalPrepayment').textContent = `${totalPrepayment.toLocaleString()} сом`;
    document.getElementById('kpiTotalAmount').textContent = `${totalAmount.toLocaleString()} сом`;
    document.getElementById('kpiCanceledBookings').textContent = canceledBookings;
  }


  // Генерация и скачивание Excel
  exportExcelBtn.addEventListener('click', () => {
    const { start, end } = reportPeriod;
    const filtered = reportRows;

    if(filtered.length === 0) {
      ui.toast('За выбранный период нет данных для выгрузки', 'warning');

      return;
    }

    const excelData = filtered.map(r => ({
      'Дата': r.date,
      'Время': r.time,
      'Столик': r.table,
      'Мероприятие': r.event,
      'Имя гостя': r.guest,
      'Кол-во гостей': r.count,
      'Сумма чека (сом)': r.total,
      'Предоплата (сом)': r.prepay,
      'Статус': STATUS_LABELS[r.status]
    }));

    // создаем книгу и лист SheetJS, скачиваем отчет
    const worksheet = XLSX.utils.json_to_sheet(excelData);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Отчет по броням');

    XLSX.writeFile(workbook, `Отчет_Пивница_${start}_${end}.xlsx`);
  });

  // загрузка с сервера и отрисовка
  async function buildReport() {
    const start = startDateInput.value;
    const end = endDateInput.value;

    if(!start || !end) {
      ui.toast('Укажите период отчёта', 'error');

      return;
    }

    applyFilterBtn.disabled = true;
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color: var(--text-muted);">Загрузка...</td></tr>`;

    try {
      reportRows = await loadReport(start, end);
      reportPeriod = { start, end };
      renderReport();
    } catch (err) {
      reportRows = [];
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color: var(--text-muted);">Не удалось сформировать отчёт: ${escapeHtml(err.message)}</td></tr>`;
      ui.toast(err.message, 'error');
    } finally {
      applyFilterBtn.disabled = false;
    }
  }

  applyFilterBtn.addEventListener('click', () => {
    if(startDateInput.value && endDateInput.value && startDateInput.value > endDateInput.value) {
      ui.toast('Дата начала периода позже даты окончания', 'error');

      return;
    }

    buildReport();
  });

  buildReport();
});