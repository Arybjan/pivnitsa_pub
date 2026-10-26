// Данный хук предназначен для проверки: "если юзер не авторизован в системе - открывается модалка входа. Если авторизован - выполнится действие"


import { useCallback } from "react";
import { useAuth } from "../context/useAuth";


interface useRequireAuthOptions {
  // функция, открывающая AuthSheet, если юзер не авторизован. Сам хук не знает про модалку, он просто ее дергает
  onNeedAuth: () => void;
}


export function useRequireAuth({ onNeedAuth }: useRequireAuthOptions) {
  const { isAuthenticated } = useAuth();


  return useCallback(
    (action: () => void) => {
      if(!isAuthenticated) {
        onNeedAuth();

        return;
      }
      // возврат функции-обертки: я передаю ей действие, она октрывает модалку для не авторизованного юзера или выполняет действие для авторизованного
      action();
    }, [isAuthenticated, onNeedAuth]);
}