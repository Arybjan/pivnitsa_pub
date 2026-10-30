import { useCallback, useSyncExternalStore, useState } from "react";
import type { Event } from "../../types/api";
import { usePublishedEvents } from "../../hooks/useEvents";
import { EventCard } from "./EventCard";
import { EventModal } from "./EventModal";
import useEmblaCarousel from 'embla-carousel-react';


export function EventCarousel() {
  const { data: eventsData, isLoading, isError } = usePublishedEvents();
  const events = eventsData?.items ?? [];

  const [selectedEvent, setSelectedEvent] = useState<Event | null>(null);


  const [emblaRef, emblaApi] = useEmblaCarousel({
    loop: false,
    align: 'start',
    containScroll: 'trimSnaps',
  });


  const subscribe = useCallback((onStoreChange: () => void) => {
    if (!emblaApi) return () => {};

    emblaApi.on('select', onStoreChange);
    emblaApi.on('reInit', onStoreChange);
    return () => {
      emblaApi.off('select', onStoreChange);
      emblaApi.off('reInit', onStoreChange);
    };
  }, [emblaApi]);

  
  const getScrollState = useCallback(() => {
    if (!emblaApi) return 0;

    return (emblaApi.canScrollPrev() ? 1 : 0) | (emblaApi.canScrollNext() ? 2 : 0);
  }, [emblaApi]);


  const scrollState = useSyncExternalStore(subscribe, getScrollState, getScrollState);
  const canScrollPrev = (scrollState & 1) !== 0;
  const canScrollNext = (scrollState & 2) !== 0;

  const scrollPrev = useCallback(() => emblaApi?.scrollPrev(), [emblaApi]);
  const scrollNext = useCallback(() => emblaApi?.scrollNext(), [emblaApi]);


  // при выборе афиши
  const handleOpen = useCallback((event: Event) => {
    setSelectedEvent(event);
  }, []);

  const handleClose = useCallback(() => {
    setSelectedEvent(null);
  }, []);


  // состояния загрузки
  if(isLoading) {
    return (
      <div className="rounded-2xl bg-tg-secondary border border-white/5 h-64 md:h-72 flex items-center justify-center animate-pulse">
        <div className="text-tg-hint text-sm">Договариваемся с гостями...</div>
      </div>
    );
  }

  if(isError) {
    return (
      <div className="rounded-2xl bg-tg-secondary border border-white/5 flex items-center justify-center py-12 px-6">
        <p className="text-tg-hint text-sm text-center">
          Не удалось загрузить афишу. Попробуйте позже.
        </p>
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div className="rounded-2xl bg-tg-secondary border border-white/5 flex items-center justify-center py-12 px-6">
        <p className="text-tg-hint text-sm text-center">
          Совсем скоро здесь появятся новые вечеринки!
        </p>
    </div>
    );
  }


  return (
    <>
      <div className="relative group/carousel">
        {/* viewport карусели - обрезает все, что вылезает */}
        <div className="overflow-hidden rounded-2xl" ref={emblaRef}>
          <div className="flex">

            {events.map((event) => (
              <div
                key={event.id}
                className="flex-[0_0_85%] sm:flex-[0_0_60%] md:flex-[0_0_45%] h-64 md:h-72 pr-3 last:pr-0"
              >
                <EventCard event={event} onOpen={handleOpen} />
              </div>
            ))}

          </div>
        </div>


        {/* стрелка влево */}
        {canScrollPrev && (
          <button
            type="button"
            onClick={scrollPrev}
            aria-label="Предыдущее мероприятие"
            className="hidden md:flex absolute left-3 top-1/2 -translate-y-1/2 z-10
                      w-11 h-11 items-center justify-center rounded-full bg-black/60
                      backdrop-blur-sm text-white opacity-0 group-hover/carousel:opacity-100
                      transition-opacity duration-200 hover:bg-black/80"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </button>
        )}

        {/* стрелка впрвао */}
        {canScrollNext && (
          <button
            type="button"
            onClick={scrollNext}
            aria-label="Следующее мероприятие"
            className="hidden md:flex absolute right-3 top-1/2 -translate-y-1/2 z-10
                      w-11 h-11 items-center justify-center rounded-full bg-black/60
                      backdrop-blur-sm text-white opacity-0 group-hover/carousel:opacity-100
                      transition-opacity duration-200 hover:bg-black/80"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>
        )}
      </div>

      <EventModal event={selectedEvent} onClose={handleClose} />
    </>
  );
}