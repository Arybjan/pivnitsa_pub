import { useState, useLayoutEffect, useEffect, useCallback, useRef } from "react";
import type { CSSProperties } from "react";

interface GuideStep {
  targetId?: string;
  image: string;
  text: string[];
  position?: 'top' | 'bottom';
  buttonText?: string;
  hideSkip?: boolean;
}

const TOUR_KEY = 'pivnitsa_tour_completed';

const STEPS: GuideStep[] = [
  {
    image: '/beery/beery_greetings.png',
    text: ['Привет! Впервые у нас? Я - твоя Кружечка пива!'],
    buttonText: 'Привет!',
    hideSkip: true,
  },
  {
    image: '/beery/beery_talking.png',
    text: ['Давай я быстро покажу, как тут всё устроено? Это займет всего минуту.'],
    buttonText: 'Давай',
  },
  {
    targetId: 'tour-worktime',
    image: '/beery/beery_proud.png',
    text: ['Наше рабочее время в Бишкеке: с 19 вечера до 5 утра.', 'Если не спится - ты по адресу!'],
    position: 'bottom',
  },
  {
    image: '/beery/beery_talking.png',
    text: ['Только главное - это... предупреждай заранее, договорились?'],
  },
  {
    targetId: 'tour-events',
    image: '/beery/beery_proud.png',
    text: ['Тут - наши тусовки и вечеринки. Даже не представляешь, как у нас весело!'],
    position: 'bottom',
  },
  {
    targetId: 'tour-events',
    image: '/beery/beery_talking.png',
    text: ['Свайпай влево-вправо, выбирай, что по душе.'],
    position: 'bottom',
  },
  {
    targetId: 'tour-events-all',
    image: '/beery/beery_proud.png',
    text: ['А если хочешь заглянуть в будущее - жми сюда!'],
    position: 'bottom',
  },
  {
    targetId: 'tour-map',
    image: '/beery/beery_talking.png',
    text: ['Выбирай этаж или дату. Зелёные столики свободны - жми на тот, который понравится, и бронируй!'],
    position: 'top',
  },
  {
    image: '/beery/beery_proud.png',
    text: ['Нас много? Не беда, мы можем сдвинуть столики.', 'Просто свяжись с нами по WhatsApp. Контакты можешь найти внизу текущего экрана.'],
  },
  {
    targetId: 'tour-mybookings',
    image: '/beery/beery_talking.png',
    text: ['Все столики, которые ты забронировал, будут лежать здесь.', 'Планы изменились? Бронь отменить можно прямо в приложении.'],
    position: 'top',
  },
  {
    image: '/beery/beery_greetings.png',
    text: ['Мы ждём тебя в любое удобное время.', 'Пока-пока!'],
    hideSkip: true,
  },
];

export function NewbieGuideline() {
  const [isActive, setIsActive] = useState(() => !localStorage.getItem(TOUR_KEY));
  const [stepIndex, setStepIndex] = useState(0);
  const [highlight, setHighlight] = useState<{ targetId: string; rect: DOMRect } | null>(null);

  const currentStep = STEPS[stepIndex];
  const targetId = currentStep.targetId;
  const rect = highlight && highlight.targetId === targetId ? highlight.rect : null;
  const noHighlight = !targetId || !rect;

  const handleClose = useCallback(() => {
    setIsActive(false);
    localStorage.setItem(TOUR_KEY, 'true');
  }, []);

  const tooltipRef = useRef<HTMLDivElement>(null);
  const [tooltipHeight, setTooltipHeight] = useState(240);

  const handleNext = useCallback(() => {
    if (stepIndex >= STEPS.length - 1) {
      handleClose();
      return;
    }

    const nextIndex = stepIndex + 1;
    const nextId = STEPS[nextIndex].targetId;
    const target = nextId ? document.getElementById(nextId) : null;

    if (target) {
      const targetHeight = target.getBoundingClientRect().height;
      target.scrollIntoView({
        behavior: 'auto',
        block: targetHeight > window.innerHeight * 0.7 ? 'start' : 'center',
        inline: 'nearest',
      });
      setHighlight({ targetId: nextId!, rect: target.getBoundingClientRect() });
    } else {
      setHighlight(null);
    }
    setStepIndex(nextIndex);
  }, [stepIndex, handleClose]);

  useLayoutEffect(() => {
    if (!isActive) return;
    const previousRestoration = window.history.scrollRestoration;
    window.history.scrollRestoration = 'manual';
    const resetScroll = () => window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
    resetScroll();
    window.addEventListener('pageshow', resetScroll);
    return () => {
      window.removeEventListener('pageshow', resetScroll);
      window.history.scrollRestoration = previousRestoration;
    };
  }, [isActive]);

  useEffect(() => {
    if (!isActive || !targetId) return;
    const target = document.getElementById(targetId);
    if (!target) return;

    let frame = 0;
    const updateRect = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        if (!target.isConnected) return;
        const next = target.getBoundingClientRect();
        setHighlight(prev => {
          if (prev?.targetId === targetId &&
              prev.rect.top === next.top && prev.rect.left === next.left &&
              prev.rect.width === next.width && prev.rect.height === next.height) return prev;
          return { targetId, rect: next };
        });
      });
    };

    const observer = new ResizeObserver(updateRect);
    observer.observe(target);
    window.addEventListener('scroll', updateRect, true);
    window.addEventListener('resize', updateRect);
    window.visualViewport?.addEventListener('resize', updateRect);
    window.visualViewport?.addEventListener('scroll', updateRect);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener('scroll', updateRect, true);
      window.removeEventListener('resize', updateRect);
      window.visualViewport?.removeEventListener('resize', updateRect);
      window.visualViewport?.removeEventListener('scroll', updateRect);
    };
  }, [isActive, targetId]);

  useEffect(() => {
    if (!isActive || noHighlight || !tooltipRef.current) return;
    const element = tooltipRef.current;
    const observer = new ResizeObserver(entries => {
      const height = entries[0]?.borderBoxSize?.[0]?.blockSize ?? element.getBoundingClientRect().height;
      setTooltipHeight(prev => Math.abs(prev - height) > 1 ? height : prev);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [isActive, noHighlight]);

  useLayoutEffect(() => {
    if (!isActive) return;

    let startX = 0;
    let startY = 0;
    const onTouchStart = (event: TouchEvent) => {
      if (event.touches.length !== 1) return;
      startX = event.touches[0].clientX;
      startY = event.touches[0].clientY;
    };
    const onTouchMove = (event: TouchEvent) => {
      if (event.touches.length !== 1) return;
      const dx = event.touches[0].clientX - startX;
      const dy = event.touches[0].clientY - startY;
      // если это скролл вверх/вниз и мы вне подсказки - блокируем
      if (Math.abs(dy) > Math.abs(dx) && event.cancelable &&
          !(event.target instanceof Node && tooltipRef.current?.contains(event.target))) {
        event.preventDefault();
      }
    };
    const onWheel = (event: WheelEvent) => {
      // если это вертикальный скролл и мы вне подсказки - блокируем
      if (Math.abs(event.deltaY) > Math.abs(event.deltaX) && event.cancelable &&
          !(event.target instanceof Node && tooltipRef.current?.contains(event.target))) {
        event.preventDefault();
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      const keys = ['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End', ' '];
      if (keys.includes(event.key) && !(event.target instanceof HTMLElement &&
          (event.target.isContentEditable || event.target.closest('button, a, input, textarea, select')))) {
        event.preventDefault();
      }
    };

    document.addEventListener('touchstart', onTouchStart, { passive: true });
    document.addEventListener('touchmove', onTouchMove, { passive: false });
    document.addEventListener('wheel', onWheel, { passive: false });
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('touchstart', onTouchStart);
      document.removeEventListener('touchmove', onTouchMove);
      document.removeEventListener('wheel', onWheel);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [isActive]);

  if (!isActive) return null;

  if (noHighlight) {
    return (
      <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/90">
        <div className="relative w-full max-w-sm bg-tg-secondary border border-white/10 rounded-3xl p-6 shadow-2xl animate-zoom-in">
          <BeeryAvatar image={currentStep.image} />
          <h3 className="text-brand font-bold text-xl mb-4 pr-12">Beery</h3>
          <TextBlock texts={currentStep.text} />
          <FooterNav
            stepIndex={stepIndex}
            totalSteps={STEPS.length}
            onNext={handleNext}
            onClose={handleClose}
            customButtonText={currentStep.buttonText}
            hideSkip={currentStep.hideSkip}
          />
        </div>
      </div>
    );
  }

  const isMobile = window.innerWidth < 768;
  const viewportHeight = window.visualViewport?.height ?? window.innerHeight;
  const highlightStyle = {
    top: rect.top - 6,
    left: rect.left - 6,
    width: rect.width + 12,
    height: rect.height + 12,
  };

  const margin = 16;
  const availableAbove = Math.max(0, rect.top - margin * 2);
  const availableBelow = Math.max(0, viewportHeight - rect.bottom - margin * 2);
  const preferTop = currentStep.position === 'top' ||
    (currentStep.position !== 'bottom' && availableBelow < tooltipHeight);
  
  const showOnTop = preferTop
    ? availableAbove >= tooltipHeight || availableAbove > availableBelow
    : availableBelow < tooltipHeight && availableAbove >= tooltipHeight;
  const fitsSide = showOnTop
    ? availableAbove >= tooltipHeight
    : availableBelow >= tooltipHeight;

  const tooltipStyle: CSSProperties = {
    left: isMobile
      ? '50%'
      : `${Math.max(200, Math.min(window.innerWidth - 200, rect.left + rect.width / 2))}px`,
    transform: 'translateX(-50%)',
    ...(fitsSide
      ? showOnTop
        ? { bottom: viewportHeight - rect.top + margin, maxHeight: Math.max(100, availableAbove) }
        : { top: rect.bottom + margin, maxHeight: Math.max(100, availableBelow) }
      : { bottom: margin, maxHeight: `calc(100dvh - ${2 * margin}px)` }),
  };

  return (
    <div className="fixed inset-0 z-[100] bg-transparent">
      <div
        className="absolute border-2 border-brand rounded-xl shadow-[0_0_0_9999px_rgba(0,0,0,0.85)] pointer-events-none"
        style={highlightStyle}
      />
      
      {/* пустое место вокруг тултипа и спрайта не перехватывает скролл (он проходит сквозь них на задний фон) */}
      <div
        className="absolute w-[calc(100vw-32px)] max-w-sm flex flex-col pointer-events-none"
        style={tooltipStyle}
      >
        {/* Спрайт теперь тоже пропускает сквозь себя события */}
        <div className="pointer-events-none">
          <BeeryAvatar image={currentStep.image} />
        </div>

        {/* Возвращаем самой подсказке pointer-events-auto, чтобы по нему можно было кликать и скроллить */}
        <div
          ref={tooltipRef}
          className="w-full bg-tg-secondary border border-white/10 rounded-3xl p-6 shadow-2xl overflow-y-auto overscroll-contain pointer-events-auto"
          style={{ maxHeight: 'inherit' }}
        >
          <h3 className="text-brand font-bold text-xl mb-4 pr-12">Beery</h3>
          
          <TextBlock texts={currentStep.text} />
          <FooterNav
            stepIndex={stepIndex}
            totalSteps={STEPS.length}
            onNext={handleNext}
            onClose={handleClose}
            customButtonText={currentStep.buttonText}
            hideSkip={currentStep.hideSkip}
          />
        </div>
      </div>
    </div>
  );
}


function BeeryAvatar({ image }: { image: string }) {
  return (
    <div className="absolute -top-16 -right-4 w-28 h-28 z-10">
      <img
        src={image}
        alt="Beery"
        className="w-full h-full object-contain drop-shadow-2xl animate-bounce-slow"
        onError={(e) => { e.currentTarget.style.display = 'none'; }}
      />
    </div>
  );
}


function TextBlock({ texts }: { texts: string[] }) {
  return (
    <div className="space-y-3 mb-6">
      {texts.map((paragraph, idx) => (
        <p key={idx} className="text-tg-text/90 text-sm leading-relaxed">
          {paragraph}
        </p>
      ))}
    </div>
  );
}


function FooterNav({ stepIndex, totalSteps, onNext, onClose, customButtonText, hideSkip }:
                  { stepIndex: number; totalSteps: number; onNext: () => void; onClose: () => void; customButtonText?: string; hideSkip?: boolean; }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-tg-hint font-semibold">
        {stepIndex + 1} / {totalSteps}
      </span>

      <div className="flex gap-2">
        {!hideSkip && (
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-tg-hint hover:text-white transition-colors"
          >
            Пропустить
          </button>
        )}

        <button
          onClick={onNext}
          className="btn btn-fancy px-6 py-2 text-sm font-bold"
        >
          {stepIndex === totalSteps - 1 ? 'Погнали!' : (customButtonText || 'Дальше')}
        </button>
      </div>
    </div>
  );
}