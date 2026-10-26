const ITEMS = [
  { color: '#22c55e', label: 'Свободен' },
  { color: '#f59e0b', label: 'Забронирован' },
  { color: '#94a3b8', label: 'Недоступен' },
];


export function Legend() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-tg-hint">
      {ITEMS.map((item) => (
        <div key={item.label} className="flex items-center gap-2">
          <span
            className="w-3 h-3 rounded-sm"
            style={{ backgroundColor: item.color }}
          />
          {item.label}
        </div>
      ))}
    </div>
  );
}