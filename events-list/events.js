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

  let currentFilter = 'all';

  // тестовые начальные данные по структуре с бэкенда
  let eventsData = JSON.parse(localStorage.getItem('eventsData')) || [
    {
      id: '1',
      title: 'Friday Techno Night: DJ Конь',
      description: 'Громкая пятничная вечеринка. Специальный сет от гостей и фирменное коктейльное меню.',
      poster_url: 'https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?w=600',
      start_time: '2026-09-18T22:00',
      end_time: '2026-09-19T04:00',
      status: 'published'
    },
    {
      id: '2',
      title: 'Acoustic Sunday & Craft Beer',
      description: 'Живой акустический вечер для ценителей хорошей музыки и редких сортов крафта.',
      poster_url: 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=600',
      start_time: '2026-09-20T19:00',
      end_time: '2026-09-20T23:00',
      status: 'draft'
    }
  ];


  function saveToStorage() {
    localStorage.setItem('eventsData', JSON.stringify(eventsData));
  }

  function renderEvents() {
    eventsGrid.innerHTML = '';

    // счетчики и фильтр
    document.getElementById('countAll').textContent = eventsData.length;
    document.getElementById('countPublished').textContent = eventsData.filter(e => e.status === 'published').length;
    document.getElementById('countDraft').textContent = eventsData.filter(e => e.status === 'draft').length;
    document.getElementById('countCancelled').textContent = eventsData.filter(e => e.status === 'cancelled').length;


    const filtered = eventsData.filter(e => currentFilter === 'all' || e.status === currentFilter);
    if(filtered.length === 0) {
      eventsGrid.innerHTML = `<div style="grid-column: 1/-1; text-align:center; color: var(--text-muted); padding: 40px;">Мероприятия не найдены</div>`;

      return;
    }

    filtered.forEach(ev => {
      const card = document.createElement('div');
      card.className = 'event-card';

      const statusLabels = {
        published: 'Опубликовано',
        draft: 'Черновик',
        cancelled: 'Снято с афиши'
      };

      const startDateFormatted = new Date(ev.start_time).toLocaleString('ru', {
        day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'
      });

      card.innerHTML = `
        <div class="poster-wrapper">
          <img src="${ev.poster_url}" alt="${ev.title}" class="poster-img" onerror="handleImageError(this)">
          <span class="status-badge status-${ev.status}">${statusLabels[ev.status]}</span>
        </div>
        <div class="event-card-body">
          <span class="event-date-time">📅 ${startDateFormatted}</span>
          <h3 class="event-title">${ev.title}</h3>
          <p class="event-desc">${ev.description || 'Без описания'}</p>
        </div>
        <div class="event-card-actions">
          <button class="btn btn-secondary btn-full" onclick="editEvent('${ev.id}')">✏️ Редактировать</button>
          ${ev.status === 'published' 
            ? `<button class="btn btn-outline-danger" onclick="toggleStatus('${ev.id}', 'cancelled')">Снять</button>` 
            : `<button class="btn btn-primary" onclick="toggleStatus('${ev.id}', 'published')">Опубликовать</button>`}
        </div>
      `;

      eventsGrid.appendChild(card);
    });
  }


  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.dataset.status;

      renderEvents();
    });
  });



  openCreateModalBtn.addEventListener('click', () => {
    eventForm.reset();

    document.getElementById('eventId').value = '';
    document.getElementById('modalTitle').textContent = 'Создать мероприятие';

    eventModal.classList.remove('hidden');
  });

  closeModalBtn.addEventListener('click', () => {
    eventModal.classList.add('hidden');
  });


  
  // изменение статуса (опубликовать / снять)
  window.toggleStatus = (id, newStatus) => {
    const ev = eventsData.find(e => e.id === id);
    if(ev) {
      ev.status = newStatus;
      
      saveToStorage();
      renderEvents();
    }
  }



  // редактирование
  window.editEvent = (id) => {
    const ev = eventsData.find(e => e.id === id);
    if(!ev) return;

    document.getElementById('eventId').value = ev.id;
    document.getElementById('eventTitle').value = ev.title;
    document.getElementById('eventPosterUrl').value = ev.poster_url;
    document.getElementById('eventStartTime').value = ev.start_time;
    document.getElementById('eventEndTime').value = ev.end_time || '';
    document.getElementById('eventDescription').value = ev.description;

    document.getElementById('modalTitle').textContent = 'Редактировать мероприятие';
    eventModal.classList.remove('hidden');
  };



  // сохранение (опубликовать / черновик)
  function saveEvent(status) {
    const id = document.getElementById('eventId').value;
    const title = document.getElementById('eventTitle').value;
    const poster_url = document.getElementById('eventPosterUrl').value;
    const start_time = document.getElementById('eventStartTime').value;
    const end_time = document.getElementById('eventEndTime').value;
    const description = document.getElementById('eventDescription').value;

    if(!title || !poster_url || !start_time) {
      alert('Пожалуйста, заполните обязательные поля!');

      return;
    }

    if(end_time && new Date(end_time) <= new Date(start_time)) {
      alert('Время окончания мероприятия должно быть позже времени начала!');

      return;
    }

    if(id) {
      // обновление существующего
      const ev = eventsData.find(e => e.id === id);
      if(ev) {
        Object.assign(ev, { title, poster_url, start_time, end_time, description, status });
      }
    } else {
      // создание нового
      eventsData.push({
        id: Date.now().toString(),
        title,
        poster_url,
        start_time,
        end_time,
        description,
        status
      });
    }

    saveToStorage();
    renderEvents();
    eventModal.classList.add('hidden');
  }



  eventForm.addEventListener('submit', (e) => {
    e.preventDefault();
    saveEvent('published');
  });

  saveDraftBtn.addEventListener('click', () => {
    saveEvent('draft');
  });

  renderEvents();

});