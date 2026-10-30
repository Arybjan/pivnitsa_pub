// без сессии администратора - на страницу входа
api.requireAuth();

document.addEventListener('DOMContentLoaded', () => {
  const userRole = localStorage.getItem('userRole') || 'admin';

  const userRoleBadge = document.getElementById('userRoleBadge');
  const reportsCard = document.getElementById('reportsCard');
  const logoutBtn = document.getElementById('logoutBtn');


  // приветствие по имени из профиля (сохраняется при входе)
  let user = null;
  try { user = JSON.parse(localStorage.getItem('user')); } catch {}

  if(user && user.first_name) {
    document.getElementById('greeting').textContent = `Здравствуйте, ${user.first_name}!`;
  }

  if(userRole === 'owner') {
    userRoleBadge.textContent = 'Владелец';
    reportsCard.classList.remove('hidden');
  } else {
    userRoleBadge.textContent = 'Администратор';
    reportsCard.classList.add('hidden');
  }


  logoutBtn.addEventListener('click', () => {
    api.logout();
  });
});