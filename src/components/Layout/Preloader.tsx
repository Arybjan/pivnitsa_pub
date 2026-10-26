import { useEffect, useId, useState } from "react";


const bubbles = Array.from({ length: 22 }, (_, i) => ({
  x: 38 + ((i * 29) % 44),
  r: 0.7 + ((i * 7) % 5) * 0.24,
  delay: -((i * 13) % 30) / 10,
  duration: 1.6 + ((i * 11) % 15) / 10,
}));


export function Preloader() {
  const [progress, setProgress] = useState(0);
  const id = useId().replace(/:/g, "");
  const clipId = `beer-clip-${id}`;
  const beerId = `beer-gradient-${id}`;
  const glassId = `glass-gradient-${id}`;
  const foamId = `foam-gradient-${id}`;


  useEffect(() => {
    const start = performance.now();
    let frame = 0;
    const tick = (now: number) => {
      const t = Math.min((now - start) / 2600, 1);
      // плавный разгон и замедление
      const eased = t * t * (3 - 2 * t);
      setProgress(eased * 100);
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, []);


  const level = 139 - (progress / 100) * 101;
  const foamOpacity = Math.min(1, Math.max(0, (progress - 10) / 22));

  
  return (
    <div className="fixed inset-0 z-[200] flex flex-col items-center justify-center bg-tg-bg text-center">
      <style>{`
        @keyframes beerBubble {
          0% { transform: translateY(0) translateX(0); opacity: 0; }
          15% { opacity: .65; }
          85% { opacity: .65; }
          100% { transform: translateY(-105px) translateX(3px); opacity: 0; }
        }
        @keyframes beerWave {
          from { transform: translateX(-12px); }
          to { transform: translateX(0px); }
        }
        @keyframes beerAppear {
          from { opacity: 0; transform: translateY(8px) scale(.97); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes foamBreathe {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-1.5px); }
        }
        .beer-bubble { animation: beerBubble var(--duration) linear var(--delay) infinite; }
        .beer-wave { animation: beerWave 1.3s ease-in-out infinite alternate; }
        .beer-foam { animation: foamBreathe 2s ease-in-out infinite; }
        .beer-enter { animation: beerAppear .5s ease-out both; }
        @media (prefers-reduced-motion: reduce) {
          .beer-bubble, .beer-wave, .beer-foam, .beer-enter { animation: none; }
        }
      `}</style>

      <div className="beer-enter mb-5 h-64 w-52 md:h-80 md:w-64">
        <svg viewBox="0 0 160 180" className="h-full w-full drop-shadow-2xl" role="img" aria-label="Кружка наполняется пивом">
          <defs>
            <clipPath id={clipId}>
              <path d="M30 30 H90 L82 130 Q82 140 72 140 H48 Q38 140 38 130 Z" />
            </clipPath>
            <linearGradient id={beerId} x1="0" y1="0" x2="0.25" y2="1">
              <stop offset="0%" stopColor="#FFE16B" />
              <stop offset="38%" stopColor="#FFC329" />
              <stop offset="100%" stopColor="#D88609" />
            </linearGradient>
            <linearGradient id={glassId} x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#E8F8FF" stopOpacity=".28" />
              <stop offset="30%" stopColor="#FFFFFF" stopOpacity=".04" />
              <stop offset="75%" stopColor="#FFFFFF" stopOpacity=".03" />
              <stop offset="100%" stopColor="#D9F5FF" stopOpacity=".3" />
            </linearGradient>
            <linearGradient id={foamId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#FFFFFF" />
              <stop offset="100%" stopColor="#F1DFB6" />
            </linearGradient>
          </defs>

          {/* стеклянная ручка позади кружки */}
          <path d="M91 47 C139 40 143 111 85 110" fill="none" stroke="#D6F3FF" strokeOpacity=".42" strokeWidth="14" strokeLinecap="round" />
          <path d="M94 50 C130 46 133 101 87 101" fill="none" stroke="#FFFFFF" strokeOpacity=".16" strokeWidth="6" strokeLinecap="round" />

          {/* внешняя форма стекла */}
          <path d="M25 25 H95 L87 135 Q87 145 77 145 H43 Q33 145 33 135 Z" fill={`url(#${glassId})`} stroke="#EAF8FF" strokeOpacity=".62" strokeWidth="3.5" strokeLinejoin="round" />

          <g clipPath={`url(#${clipId})`}>
            {/* жидкость, поднимающаяся снизу */}
            <rect x="25" y={level} width="75" height={145 - level} fill={`url(#${beerId})`} />

            {/* мягкая волна на поверхности */}
            {progress > 1 && (
              <g className="beer-wave">
                <path d={`M20 ${level + 1} Q32 ${level - 2} 44 ${level + 1} T68 ${level + 1} T92 ${level + 1} H110 V${level + 8} H20 Z`} fill="#FFE58A" opacity=".65" />
              </g>
            )}

            {/* пузырьки появляются только внутри пива */}
            <svg x="25" y={level + 3} width="75" height={Math.max(0, 139 - level - 3)} viewBox={`25 ${level + 3} 75 ${Math.max(1, 139 - level - 3)}`} overflow="hidden">
              {bubbles.map((bubble, i) => (
                <circle
                  key={i}
                  className="beer-bubble"
                  cx={bubble.x}
                  cy="145"
                  r={bubble.r}
                  fill="#FFF5C9"
                  style={{ "--duration": `${bubble.duration}s`, "--delay": `${bubble.delay}s` } as React.CSSProperties}
                />
              ))}
            </svg>

            {/* пена растёт вместе с поверхностью */}
            {progress > 10 && (
              <g className="beer-foam" opacity={foamOpacity}>
                <path d={`M27 ${level + 3} Q33 ${level - 7} 42 ${level - 4} Q51 ${level - 13} 61 ${level - 6} Q72 ${level - 13} 82 ${level - 5} Q90 ${level - 7} 95 ${level + 2} V${level + 9} H27 Z`} fill={`url(#${foamId})`} />
                <circle cx="42" cy={level - 3} r="4" fill="#FFF9EA" />
                <circle cx="58" cy={level - 7} r="5" fill="#FFFDF5" />
                <circle cx="76" cy={level - 5} r="4" fill="#FFF9EA" />
                <circle cx="51" cy={level - 5} r="1.1" fill="#DCCCA7" opacity=".55" />
                <circle cx="68" cy={level - 3} r=".9" fill="#DCCCA7" opacity=".55" />
              </g>
            )}
          </g>

          {/* блики поверх жидкости */}
          <path d="M37 35 L43 35 L40 122 L35 126 Z" fill="#FFFFFF" opacity=".23" />
          <path d="M88 36 L91 36 L84 126 L82 128 Z" fill="#FFFFFF" opacity=".15" />
          <path d="M35 134 Q36 144 46 144 H76 Q85 144 86 134" fill="none" stroke="#E8F8FF" strokeOpacity=".45" strokeWidth="4" />
          <path d="M26 25 H94" stroke="#FFFFFF" strokeOpacity=".75" strokeWidth="3" strokeLinecap="round" />
        </svg>
      </div>

      <p className="text-tg-hint text-lg font-bold tracking-widest uppercase md:text-xl" aria-live="polite">
        {progress >= 100 ? "За ваше здоровье! 🍻" : "Наливаем пиво..."}
      </p>
    </div>
  );
}
