import type { MapTable } from "../../types/api";
import { CONFIG } from "../../lib/config"; // для перевода координат 0...1 в px


// визуальные статусы для гостя
type UiStatus = 'free' | 'booked' | 'unavailable';
const STATUS_COLORS: Record<UiStatus, string> = {
  free: '#22c55e',
  booked: '#f59e0b',
  unavailable: '#94a3b8',
};

interface TableShapeProps {
  table: MapTable;
  isSelected?: boolean;
  onSelect: (table: MapTable) => void;
}


export function TableShape({ table, isSelected, onSelect }: TableShapeProps) {
  // в админ-панели originX/originY = 'center' (x/y - центр стола). В SVG <rect> работает от левого верхнего угла
  // другими словами: в админ-панели Fabric.js хранит центр, а в SVG <rect> - угол. Конвертируем:
  // const x = table.x - table.width / 2;
  // const y = table.y - table.height / 2;

  // так как backend написан не в px, а в процентах:
  const { width: baseW, height: baseH } = CONFIG.HALL_VIEWBOX;
  // переводим координаты из 0...1 в px (900x550 canvas)
  const pxX = table.x * baseW;
  const pxY = table.y * baseH;
  // размер стола (null = 10% от ш/в)
  const pxWidth = (table.width || 0.1) * baseW;
  const pxHeight = (table.height || 0.1) * baseH;
  // в SVG рисуем от левого верхнего угла, ибо так создано в бэкенде
  const rectX = pxX;
  const rectY = pxY;
  const textX = pxX + pxWidth / 2;
  const textY = pxY + pxHeight / 2;


  // визуальный статус для гостя
  let uiStatus: UiStatus = 'free';

  if(table.status === 'UNAVAILABLE' || table.occupied) uiStatus = 'unavailable';
  else if(table.physically_available === false) uiStatus = 'booked';


  // только свободные столы реагируют на клик
  const isClickable = uiStatus === 'free';
  const color = STATUS_COLORS[uiStatus];


  return (
    // вся группа кликабельна как одно целое
    <g
      onClick={() => isClickable && onSelect(table)}
      style={{ cursor: isClickable ? 'pointer' : 'not-allowed' }}
    >
      <rect
        x={rectX}
        y={rectY}
        width={pxWidth}
        height={pxHeight}
        rx={8}
        ry={8}
        fill={color}
        stroke={isSelected ? '#fec200' : '#ffffff'}
        strokeWidth={isSelected ? 3 : 1}
        opacity={isClickable ? 1 : 0.55}
      />

      {/* текст внутри (номер и вместимость столика) */}
      <text
        x={textX}
        y={textY}
        textAnchor="middle"
        dominantBaseline="middle"
        fill="#ffffff"
        fontFamily="system-ui, sans-serif"
        fontSize={14}
        fontWeight={600}
        style={{ pointerEvents: 'none', userSelect: 'none' }}
      >
        <tspan x={textX} dy='-0.3em'>
          №{table.number}
        </tspan>
        <tspan x={textX} dy='1.2em' fontSize={12} fontWeight={400}>
          Мест: {table.capacity}
        </tspan>
      </text>
    </g>
  );
}