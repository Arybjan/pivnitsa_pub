// Общие уведомления и диалоги вместо alert / confirm / prompt
// ui.toast('Текст', 'success' | 'error' | 'warning' | 'info')
// await ui.confirm({ title, message, okText, danger }) -> true / false
// await ui.prompt({ title, message, placeholder, options, okText }) -> строка или null (отмена)

const ui = (() => {
  const ICONS = { success: '✓', error: '!', warning: '!', info: 'i' };

  let toastStack;


  // Тосты
  function toast(message, type = 'info', duration = 3000) {
    if(!toastStack) {
      toastStack = document.createElement('div');
      toastStack.className = 'ui-toast-stack';
      toastStack.setAttribute('aria-live', 'polite');

      document.body.appendChild(toastStack);
    }

    const el = document.createElement('div');
    el.className = `ui-toast ${type}`;
    el.setAttribute('role', type === 'error' ? 'alert' : 'status');

    const icon = document.createElement('span');
    icon.className = 'ui-toast-icon';
    icon.textContent = ICONS[type] || ICONS.info;

    const text = document.createElement('span');
    text.textContent = message;

    el.append(icon, text);
    toastStack.appendChild(el);

    const remove = () => {
      el.classList.add('leaving');
      setTimeout(() => el.remove(), 200);
    };

    el.addEventListener('click', remove); // закрытие по клику
    setTimeout(remove, duration);
  }



  // Базовый диалог (подтверждение и ввод текста)
  function dialog({ title, message = '', okText = 'OK', cancelText = 'Отмена', danger = false, input = null }) {
    return new Promise((resolve) => {
      const lastFocused = document.activeElement;

      const backdrop = document.createElement('div');
      backdrop.className = 'ui-dialog-backdrop';

      const box = document.createElement('div');
      box.className = 'ui-dialog';
      box.setAttribute('role', 'dialog');
      box.setAttribute('aria-modal', 'true');

      const h = document.createElement('h3');
      h.textContent = title;
      box.appendChild(h);

      if(message) {
        const p = document.createElement('p');
        p.textContent = message;
        box.appendChild(p);
      }

      let field;
      if(input) {
        // быстрые варианты ответа (чипы)
        if(input.options && input.options.length) {
          const chips = document.createElement('div');
          chips.className = 'ui-dialog-chips';

          input.options.forEach(opt => {
            const chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'ui-chip';
            chip.textContent = opt;

            chip.addEventListener('click', () => {
              field.value = opt;
              chips.querySelectorAll('.ui-chip').forEach(c => c.classList.toggle('active', c === chip));
              field.focus();
            });

            chips.appendChild(chip);
          });

          box.appendChild(chips);
        }

        field = document.createElement('input');
        field.type = 'text';
        field.className = 'ui-dialog-input';
        field.placeholder = input.placeholder || '';
        field.value = input.value || '';

        box.appendChild(field);
      }

      const actions = document.createElement('div');
      actions.className = 'ui-dialog-actions';

      const cancelBtn = document.createElement('button');
      cancelBtn.type = 'button';
      cancelBtn.className = 'ui-btn ghost';
      cancelBtn.textContent = cancelText;

      const okBtn = document.createElement('button');
      okBtn.type = 'button';
      okBtn.className = `ui-btn ${danger ? 'danger' : 'primary'}`;
      okBtn.textContent = okText;

      actions.append(cancelBtn, okBtn);
      box.appendChild(actions);
      backdrop.appendChild(box);
      document.body.appendChild(backdrop);


      function close(result) {
        document.removeEventListener('keydown', onKey, true);
        backdrop.remove();

        if(lastFocused && lastFocused.focus) lastFocused.focus();
        resolve(result);
      }

      const ok = () => close(input ? field.value.trim() : true);
      const cancel = () => close(input ? null : false);

      // Esc - отмена, Enter - подтверждение (перехватываем раньше страницы)
      function onKey(e) {
        if(e.key === 'Escape') {
          e.stopPropagation();
          cancel();
        } else if(e.key === 'Enter') {
          e.preventDefault();
          e.stopPropagation();
          ok();
        }
      }

      okBtn.addEventListener('click', ok);
      cancelBtn.addEventListener('click', cancel);
      backdrop.addEventListener('mousedown', (e) => {
        if(e.target === backdrop) cancel();
      });
      document.addEventListener('keydown', onKey, true);

      (field || okBtn).focus();
    });
  }

  function confirm(options) {
    return dialog({ okText: 'Подтвердить', ...options });
  }

  function prompt({ placeholder, options, value, ...rest }) {
    return dialog({ okText: 'Сохранить', ...rest, input: { placeholder, options, value } });
  }



  // Модальные окна страниц: закрытие по Esc и клику по затемнению
  // (нажимаем на их собственную кнопку закрытия, чтобы сработала логика страницы)
  function closeTopModal() {
    const openModals = [...document.querySelectorAll('.modal-backdrop:not(.hidden)')];
    const top = openModals[openModals.length - 1];
    if(!top) return false;

    const closeBtn = top.querySelector('.btn-close');
    if(closeBtn) closeBtn.click();
    else top.classList.add('hidden');

    return true;
  }

  document.addEventListener('keydown', (e) => {
    if(e.key === 'Escape') closeTopModal();
  });

  document.addEventListener('mousedown', (e) => {
    if(e.target.classList && e.target.classList.contains('modal-backdrop')) closeTopModal();
  });


  return { toast, confirm, prompt };
})();
