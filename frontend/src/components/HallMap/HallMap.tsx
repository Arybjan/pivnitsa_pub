import type { MapTable } from "../../types/api";
import { CONFIG } from "../../lib/config";
import { TableShape } from "./TableShape";
import { Legend } from "./Legend";
import { TransformWrapper, TransformComponent } from "react-zoom-pan-pinch";


interface HallMapProps {
  tables: MapTable[];
  selectedTableId?: number;
  onSelectTable: (table: MapTable) => void;
}


function ZoomBtn({ onClick, label, children }: { onClick: () => void; label: string; children: React.ReactNode; }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className="w-8 h-8 flex items-center justify-center rounded-lg bg-black/60 backdrop-blur-sm text-white hover:bg-black/80 transition-colors"
    >
      {children}
    </button>
  );
}


export function HallMap({ tables, selectedTableId, onSelectTable }: HallMapProps) {
  // canvas 900x550
  const { width, height } = CONFIG.HALL_VIEWBOX;

  if(tables.length === 0) {
    return (
      <div className="aspect-[9/5.5] flex items-center justify-center rounded-2xl bg-tg-secondary text-tg-hint text-sm">
        На этом этаже пока нет столиков.
      </div>
    );
  }


  return (
    <div className="flex flex-col gap-3">
      <div className="relative rounded-2xl bg-tg-secondary overflow-hidden">
        <TransformWrapper // слушает жесты, хранит scale/offset
          minScale={0.8}
          maxScale={3}
          initialScale={1}
          doubleClick={{ disabled: true }}
          wheel={{ step: 0.15 }}
          pinch={{ step: 3 }}
        >
          {({ zoomIn, zoomOut, resetTransform }) => (
            <>
              <TransformComponent // визуальный компонент, к которому применяется transform
                // ! - нужно, ибо react-zoom-pan-pinch по умолчанию ставит width: fit-content на обертку (нам нужно, чтобы она занимала всю ширину родителя)
                wrapperClass="!w-full !h-full"
                contentClass="!w-full"
              >
                <svg
                  viewBox={`0 0 ${width} ${height}`}
                  preserveAspectRatio="xMidYMid meet" // svg масштабируется пропорционально, вписывается в контейнер
                  className="w-full h-auto block" // block убирает пустоту под картой (инлайновый отступ снизу от <svg>)
                >
                  <defs>
                    {/* паттерн фона из точек, как в dashboard.css */}
                    <pattern 
                      id="hall-dots"
                      x='0'
                      y='0'
                      width='20'
                      height='20'
                      patternUnits="userSpaceOnUse"
                    >
                      <circle cx='1' cy='1' r='1' fill='rgba(255, 255, 255, 0.06)' />
                    </pattern>
                  </defs>

                  <rect width={width} height={height} fill="url(#hall-dots)" />

                  {tables.map((table) => (
                    <TableShape
                      key={table.id}
                      table={table}
                      isSelected={table.id === selectedTableId}
                      onSelect={onSelectTable}
                    />
                  ))}
                </svg>
              </TransformComponent>

              {/* кнокпи зума для десктопа и на всякий */}
              <div className="absolute bottom-3 right-3 flex gap-1.5 z-10">
                <ZoomBtn onClick={() => zoomOut()} label='Уменьшить'>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                    <line x1="5" y1="12" x2="19" y2="12" />
                  </svg>
                </ZoomBtn>

                <ZoomBtn onClick={() => resetTransform()} label='Сбросить'>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
                    <polyline points="3 3 3 8 8 8" />
                  </svg>
                </ZoomBtn>

                <ZoomBtn onClick={() => zoomIn()} label='Увеличить'>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                    <line x1="12" y1="5" x2="12" y2="19" />
                    <line x1="5" y1="12" x2="19" y2="12" />
                  </svg>
                </ZoomBtn>
              </div>
            </>
          )}
        </TransformWrapper>
      </div>

      <Legend />
    </div>
  );
}