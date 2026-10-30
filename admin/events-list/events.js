// без сессии администратора - на страницу входа
api.requireAuth();

// заглушка афиши
const svgContent = `
<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">
  <rect width="100%" height="100%" fill="#121212"/>
  <text x="50%" y="50%" fill="#a1a1aa" font-family="system-ui, sans-serif" font-size="22" font-weight="500" text-anchor="middle" dominant-baseline="middle">Нет афиши</text>
</svg>`.trim();

const default_poster = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svgContent)}`;

window.handleImageError = (img) => {
  img.onerror = null; // отключение повторного вызова от цикла
  img.src = default_poster;
};



document.addEventListener('DOMContentLoaded', () => {

  const eventsGrid = document.getElementById('eventsGrid');
  const openCreateModalBtn = document.getElementById('openCreateModalBtn');
  const closeModalBtn = document.getElementById('closeModalBtn');
  const eventModal = document.getElementById('eventModal');
  const eventForm = document.getElementById('eventForm');
  const saveDraftBtn = document.getElementById('saveDraftBtn');
  const filterBtns = document.querySelectorAll('.filter-btn');

  // последняя открытая вкладка фильтра
  let currentFilter = 'all';
  try {
    currentFilter = localStorage.getItem('eventsFilter') || 'all';
  } catch {}

  filterBtns.forEach(b => b.classList.toggle('active', b.dataset.status === currentFilter));

  let eventsData = [];
  let isLoading = true;
  let loadError = '';

  // иконки кнопок карточки (цвет берётся из цвета текста кнопки)
  const icon = (path) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${path}</svg>`;

  const ICONS = {
    edit: icon('<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>'),
    publish: icon('<path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4Z"/>'),
    hide: icon('<path d="M9.9 4.2A9 9 0 0 1 12 4c7 0 10 8 10 8a13 13 0 0 1-1.7 2.7"/><path d="M6.6 6.6A13 13 0 0 0 2 12s3 8 10 8a9 9 0 0 0 5.4-1.6"/><path d="m2 2 20 20"/>'),
    cancel: icon('<path d="M18 6 6 18"/><path d="m6 6 12 12"/>')
  };

  const statusLabels = {
    published: 'Опубликовано',
    draft: 'Черновик',
    cancelled: 'Отменено',
    finished: 'Завершено'
  };


  // экранирование текста с сервера перед вставкой в HTML
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[ch]);

  // ISO (UTC) с бэкенда -> значение для datetime-local по местному времени
  const toLocalInput = (iso) => {
    if(!iso) return '';

    const date = new Date(iso);
    const pad = (n) => String(n).padStart(2, '0');

    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  };

  // datetime-local (местное время) -> ISO с часовым поясом для бэкенда
  const toIso = (value) => value ? new Date(value).toISOString() : null;

  // EventOut с бэкенда -> формат карточки
  const fromApi = (ev) => ({
    id: String(ev.id),
    title: ev.title,
    description: ev.description || '',
    poster_url: ev.poster_url || '',
    start_time: ev.starts_at,
    end_time: ev.ends_at,
    status: ev.status.toLowerCase()
  });


  // загрузка всех мероприятий (бэкенд отдаёт максимум 100 за запрос)
  async function loadEvents() {
    const items = [];
    let offset = 0;
    let page;

    do {
      page = await api.request('event', `/api/v1/events/all?limit=100&offset=${offset}`);
      items.push(...page.items);
      offset += page.items.length;
    } while(page.has_next && page.items.length);

    eventsData = items.map(fromApi);
  }

  async function refreshEvents() {
    try {
      await loadEvents();
      loadError = '';
    } catch (err) {
      loadError = err.message;
      ui.toast(err.message, 'error');
    } finally {
      isLoading = false;
      renderEvents();
    }
  }

  // замена одного мероприятия в списке после ответа сервера
  function upsertEvent(apiEvent) {
    const ev = fromApi(apiEvent);
    const index = eventsData.findIndex(e => e.id === ev.id);

    if(index === -1) eventsData.unshift(ev);
    else eventsData[index] = ev;
  }


  function renderEvents() {
    eventsGrid.innerHTML = '';

    // счетчики и фильтр
    document.getElementById('countAll').textContent = eventsData.length;
    document.getElementById('countPublished').textContent = eventsData.filter(e => e.status === 'published').length;
    document.getElementById('countDraft').textContent = eventsData.filter(e => e.status === 'draft').length;
    document.getElementById('countCancelled').textContent = eventsData.filter(e => e.status === 'cancelled').length;


    const emptyState = (text) => `<div style="grid-column: 1/-1; text-align:center; color: var(--text-muted); padding: 40px;">${escapeHtml(text)}</div>`;

    if(isLoading) {
      eventsGrid.innerHTML = emptyState('Загрузка мероприятий...');

      return;
    }

    if(loadError) {
      eventsGrid.innerHTML = emptyState(`Не удалось загрузить мероприятия: ${loadError}`);

      return;
    }

    const filtered = eventsData.filter(e => currentFilter === 'all' || e.status === currentFilter);
    if(filtered.length === 0) {
      eventsGrid.innerHTML = emptyState('Мероприятия не найдены');

      return;
    }

    filtered.forEach(ev => {
      const card = document.createElement('div');
      card.className = 'event-card';

      const startDateFormatted = new Date(ev.start_time).toLocaleString('ru', {
        day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'
      });

      // отменённые и завершённые больше не меняются
      const isClosed = ev.status === 'cancelled' || ev.status === 'finished';

      const editBtn = `<button class="btn btn-secondary btn-grow" onclick="editEvent('${ev.id}')">${ICONS.edit}Изменить</button>`;

      const actions = {
        published: `${editBtn}
          <button class="btn btn-outline-danger" onclick="toggleStatus('${ev.id}', 'draft')">${ICONS.hide}Снять с афиши</button>`,
        draft: `<button class="btn btn-primary btn-grow" onclick="toggleStatus('${ev.id}', 'published')">${ICONS.publish}Опубликовать</button>
          <button class="btn btn-secondary" onclick="editEvent('${ev.id}')">${ICONS.edit}Изменить</button>
          <button class="btn btn-outline-danger btn-icon" onclick="toggleStatus('${ev.id}', 'cancelled')" title="Отменить мероприятие" aria-label="Отменить мероприятие">${ICONS.cancel}</button>`
      };

      const closedNote = ev.status === 'cancelled' ? 'Мероприятие отменено' : 'Мероприятие завершено';

      card.innerHTML = `
        <div class="poster-wrapper">
          <img src="${escapeHtml(ev.poster_url)}" alt="${escapeHtml(ev.title)}" class="poster-img" onerror="handleImageError(this)">
          <span class="status-badge status-${ev.status}">${statusLabels[ev.status]}</span>
        </div>
        <div class="event-card-body">
          <span class="event-date-time">📅 ${startDateFormatted}</span>
          <h3 class="event-title">${escapeHtml(ev.title)}</h3>
          <p class="event-desc">${escapeHtml(ev.description || 'Без описания')}</p>
        </div>
        ${isClosed
          ? `<div class="event-card-actions event-card-closed">${closedNote}</div>`
          : `<div class="event-card-actions">${actions[ev.status]}</div>`}
      `;

      eventsGrid.appendChild(card);
    });
  }


  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.dataset.status;
      try { localStorage.setItem('eventsFilter', currentFilter); } catch {}

      renderEvents();
    });
  });



  openCreateModalBtn.addEventListener('click', () => {
    eventForm.reset();

    document.getElementById('eventId').value = '';
    document.getElementById('modalTitle').textContent = 'Создать мероприятие';

    eventModal.classList.remove('hidden');
    document.getElementById('eventTitle').focus();
  });

  closeModalBtn.addEventListener('click', () => {
    eventModal.classList.add('hidden');
  });


  
  // смена статуса на бэкенде: published -> /publish, draft -> /unpublish, cancelled -> /cancel
  const STATUS_ACTIONS = { published: 'publish', draft: 'unpublish', cancelled: 'cancel' };

  function changeStatus(id, newStatus) {
    return api.request('event', `/api/v1/events/${id}/${STATUS_ACTIONS[newStatus]}`, { method: 'POST' });
  }


  // изменение статуса (опубликовать / снять / отменить)
  window.toggleStatus = async (id, newStatus) => {
    const ev = eventsData.find(e => e.id === id);
    if(!ev) return;

    if(newStatus === 'draft') {
      const ok = await ui.confirm({
        title: 'Снять с афиши?',
        message: `«${ev.title}» перестанет отображаться у гостей и вернётся в черновики. Опубликовать снова можно в любой момент.`,
        okText: 'Снять',
        danger: true
      });

      if(!ok) return;
    }

    if(newStatus === 'cancelled') {
      const ok = await ui.confirm({
        title: 'Отменить мероприятие?',
        message: `«${ev.title}» будет отменено окончательно, опубликовать его снова будет нельзя.`,
        okText: 'Отменить мероприятие',
        cancelText: 'Не отменять',
        danger: true
      });

      if(!ok) return;
    }

    try {
      upsertEvent(await changeStatus(id, newStatus));
    } catch (err) {
      ui.toast(err.message, 'error');

      return;
    }

    renderEvents();

    const messages = {
      published: 'Мероприятие опубликовано',
      draft: 'Мероприятие снято с афиши',
      cancelled: 'Мероприятие отменено'
    };
    ui.toast(messages[newStatus], 'success');
  }



  // редактирование
  window.editEvent = (id) => {
    const ev = eventsData.find(e => e.id === id);
    if(!ev) return;

    document.getElementById('eventId').value = ev.id;
    document.getElementById('eventTitle').value = ev.title;
    document.getElementById('eventPosterUrl').value = ev.poster_url;
    document.getElementById('eventStartTime').value = toLocalInput(ev.start_time);
    document.getElementById('eventEndTime').value = toLocalInput(ev.end_time);
    document.getElementById('eventDescription').value = ev.description;

    document.getElementById('modalTitle').textContent = 'Редактировать мероприятие';
    eventModal.classList.remove('hidden');
  };



  // сохранение (опубликовать / черновик)
  async function saveEvent(status) {
    const id = document.getElementById('eventId').value;
    const title = document.getElementById('eventTitle').value.trim();
    const poster_url = document.getElementById('eventPosterUrl').value.trim();
    const start_time = document.getElementById('eventStartTime').value;
    const end_time = document.getElementById('eventEndTime').value;
    const description = document.getElementById('eventDescription').value;

    if(!title || !poster_url || !start_time) {
      ui.toast('Заполните обязательные поля: название, афиша и время начала', 'error');

      return;
    }

    if(end_time && new Date(end_time) <= new Date(start_time)) {
      ui.toast('Время окончания должно быть позже времени начала', 'error');

      return;
    }

    const payload = {
      title,
      poster_url,
      description: description.trim() || null,
      starts_at: toIso(start_time),
      ends_at: toIso(end_time)
    };

    const buttons = [saveDraftBtn, document.getElementById('publishBtn')];
    buttons.forEach(b => b.disabled = true);

    try {
      let saved;

      if(id) {
        // обновление существующего, затем смена статуса, если нужна
        saved = await api.request('event', `/api/v1/events/${id}`, { method: 'PATCH', body: payload });
      } else {
        // новое мероприятие на бэкенде всегда создаётся черновиком
        saved = await api.request('event', '/api/v1/events', { method: 'POST', body: payload });
      }

      upsertEvent(saved);

      if(saved.status.toLowerCase() !== status) {
        upsertEvent(await changeStatus(saved.id, status));
      }
    } catch (err) {
      ui.toast(err.message, 'error');

      // данные могли сохраниться частично (например, создано, но не опубликовано)
      await refreshEvents();

      return;
    } finally {
      buttons.forEach(b => b.disabled = false);
    }

    renderEvents();
    eventModal.classList.add('hidden');

    ui.toast(status === 'published' ? 'Мероприятие сохранено и опубликовано' : 'Сохранено как черновик', 'success');
  }



  eventForm.addEventListener('submit', (e) => {
    e.preventDefault();
    saveEvent('published');
  });

  saveDraftBtn.addEventListener('click', () => {
    saveEvent('draft');
  });

  renderEvents();
  refreshEvents();

});