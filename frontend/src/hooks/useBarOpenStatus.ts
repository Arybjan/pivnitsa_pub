// Данный хук с таймером предназначен для автоматического ежеминутного обновления статуса "Открыто/Закрыто"


import { useEffect, useState } from "react";
import { isBarOpenNow } from "../lib/date";


export function useBarOpenStatus(): boolean {
  // при первом же рендере получаем правильное значение
  const [isOpen, setIsOpen] = useState(isBarOpenNow);

  useEffect(() => {
    const id = setInterval(() => {
      setIsOpen(isBarOpenNow);
    }, 60_000);

    return () => clearInterval(id);
  }, []);

  return isOpen;
}