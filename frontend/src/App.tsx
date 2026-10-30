import { HomePage } from './pages/HomePage';
import { EventsListPage } from './pages/EventsListPage';
import { AuthProvider } from './context/AuthContext';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ProfilePage } from './pages/ProfilePage';
import { MyReservationsPage } from './pages/MyReservationsPage';

function App() {
  return (
    // весь роутинг должен быть внутри провайдера, чтобы страницы могли использовать useAuth
    <AuthProvider>
      {/* работает везде, использует #/hall (часть после # не уходит на сервер, а обрабатывается браузером на клиенте) */}
      <HashRouter>
        <Routes>
  
          <Route path='/' element={<HomePage />} />
          <Route path='/events' element={<EventsListPage />} />
          <Route path='/profile' element={<ProfilePage />} />
          <Route path='/my' element={<MyReservationsPage />} />
          
          {/* Остальное - на главную */}
          <Route path='*' element={<Navigate to='/' replace />} />
  
        </Routes>
      </HashRouter>
    </AuthProvider>
  );
}

export default App;