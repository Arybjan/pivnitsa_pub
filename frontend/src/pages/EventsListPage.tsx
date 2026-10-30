import { Link } from "react-router-dom";
import { EventListItem } from "../components/EventCarousel/EventListItem";
import { usePublishedEvents } from "../hooks/useEvents";
import type { Event } from "../types/api";


export function EventsListPage() {
  // вызываем хук для получения данных
  const { data: eventsData, isLoading, isError } = usePublishedEvents();
  // безопасно достаем по умолчанию пустой массив
  const events = eventsData?.items ?? [];


  const handleOpen = (event: Event) => {
    console.log('open event', event.id)
  };


  return (
    <div className="min-h-screen bg-tg-bg text-tg-text flex flex-col">
      <div className="w-full max-w-3xl mx-auto flex-1 flex flex-col">

        <header className="px-5 pt-8 pb-5">
          <Link
            to='/'
            className="inline-flex items-center gap-1 text-tg-hint hover:text-brand transition-colors text-sm mb-4"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            Назад
          </Link>

          <h1 className="text-2xl font-bold tracking-tight">Все мероприятия</h1>
        </header>

        {/* вертикальный список, состояния */}
        <section className="px-5 pb-10 flex flex-col gap-4">
          {isLoading && (
            <div className="flex flex-col gap-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-28 bg-tg-secondary rounded-2xl animate-pulse" />
              ))}
            </div>
          )}

          {isError && (
            <p className="text-tg-hint text-sm text-center py-12">
              Не удалось загрузить мероприятия. Проверьте подключение.
            </p>
          )}

          {!isLoading && !isError && events.length === 0 && (
            <p className="text-tg-hint text-sm text-center py-12">
              Мероприятий пока нет :/
            </p>
          )}

          {!isLoading && !isError && events.length > 0 && (
            events.map((event, index) => (
              <div
                key={event.id}
                className="animate-fade-in-up"
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <EventListItem event={event} onOpen={handleOpen}  />
              </div>
            ))
          )}
        </section>

        {/* пагинация с "Показать еще" или бесконечная прокрутка */}
      </div>
    </div>
  );
}