document.addEventListener('DOMContentLoaded', () => {
  const userRole = localStorage.getItem('userRole') || 'admin';

  const userRoleBadge = document.getElementById('userRoleBadge');
  const reportsCard = document.getElementById('reportsCard');
  const logoutBtn = document.getElementById('logoutBtn');


  if(userRole === 'owner') {
    userRoleBadge.textContent = 'Владелец';
    reportsCard.classList.remove('hidden');
  } else {
    userRoleBadge.textContent = 'Администратор';
    reportsCard.classList.add('hidden');
  }


  logoutBtn.addEventListener('click', () => {
    localStorage.clear();
    window.location.href = '../login-form/index.html';
  });
});