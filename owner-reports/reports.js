document.addEventListener('DOMContentLoaded', () => {
  const userRole = localStorage.getItem('userRole') || 'admin';

  if(userRole !== 'owner') {
    alert('Доступ запрещен. Страница только для Владельца!');
    window.location.href = '../main-menu/main.html';

    return;
  }


  const startDateInput = document.getElementById('startDate');
  const endDateInput = document.getElementById('endDate');
  const applyFilterBtn = document.getElementById('applyFilterBtn');
  const exportExcelBtn = document.getElementById('exportExcelBtn');
  const tbody = document.getElementById('reportsTableBody');


  // Диапазон по умолчанию (текущий месяц)
  const now = new Date();
  const firstDay = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0];
  const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split('T')[0];

  startDateInput.value = firstDay;
  endDateInput.value = lastDay;


  // тестовые данные (без бэкенда)
  const testReportData = [
    { date: '2026-09-01', time: '18:00', table: 'Стол №1', guest: 'Иван', count: 2, total: 3000, prepay: 500, status: 'active' },
    { date: '2026-09-03', time: '20:00', table: 'Стол №4', guest: 'Мария', count: 6, total: 12000, prepay: 2000, status: 'active' },
    { date: '2026-09-05', time: '19:30', table: 'Стол №2', guest: 'Данияр', count: 4, total: 5000, prepay: 1000, status: 'canceled' },
    { date: '2026-09-08', time: '19:00', table: 'Стол №2', guest: 'Алексей', count: 4, total: 5000, prepay: 1000, status: 'active' },
    { date: '2026-09-10', time: '21:00', table: 'Стол №5', guest: 'Елена', count: 8, total: 15000, prepay: 3000, status: 'active' }
  ];


  // фильтрация и отрисовка
  function renderReport() {
    const start = startDateInput.value;
    const end = endDateInput.value;

    const filtered = testReportData.filter(r => r.date >= start && r.date <= end);

    let totalBookings = filtered.length;
    let totalPrepayment = 0;
    let totalAmount = 0;
    let canceledBookings = 0;

    tbody.innerHTML = '';

    if(filtered.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color: var(--text-muted);">За выбранный период данных нет</td></tr>`;
    }

    filtered.forEach(r => {
      if(r.status === 'active') {
        totalPrepayment += r.prepay;
        totalAmount += r.total;
      } else canceledBookings++;

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${r.date}</td>
        <td>${r.time}</td>
        <td>${r.table}</td>
        <td>${r.guest}</td>
        <td>${r.count} чел</td>
        <td>${r.total} сом</td>
        <td>${r.prepay} сом</td>
        <td>
          <span class="badge ${r.status === 'active' ? 'badge-success' : 'badge-danger'}">
            ${r.status === 'active' ? 'Успешно' : 'Отменено'}
          </span>
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
    const start = startDateInput.value;
    const end = endDateInput.value;
    const filtered = testReportData.filter(r => r.date >= start && r.date <= end);

    if(filtered.length === 0) {
      alert('Нет данных для выгрузки!');

      return;
    }

    const excelData = filtered.map(r => ({
      'Дата': r.date,
      'Время': r.time,
      'Столик': r.table,
      'Имя гостя': r.guest,
      'Кол-во гостей': r.count,
      'Сумма чека (сом)': r.total,
      'Предоплата (сом)': r.prepay,
      'Статус': r.status === 'active' ? 'Успешно' : 'Отменена'
    }));

    // создаем книгу и лист SheetJS, скачиваем отчет
    const worksheet = XLSX.utils.json_to_sheet(excelData);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Отчет по броням');

    XLSX.writeFile(workbook, `Отчет_Пивница_${start}_${end}.xlsx`);
  });

  applyFilterBtn.addEventListener('click', renderReport);

  renderReport();
});