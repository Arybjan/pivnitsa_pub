// ФАЙЛ ДЕКЛАРАЦИЙ TS (только для редактора и компилятора)
// описываются типы, не превращающиеся в JS при сборке,
// так как TS не знает про глобальные объекты, которых нет в стандартных библиотеках, а значит ругается на них
// например, window.Telegram не в DOM-стандарте. Это расширение, которое добавляет TG WebApp SDK в рантайме


export {}; // делает файл модулем, иначе TS посчитает global глобальным скриптом

declare global { // все, что внутри, TS добавит в глобальную область
  interface Window { // расширение стандартного Window дополнительным полем Telegram? (? - опциональное поле, вне TG его нет)
    Telegram?: {
      WebApp?: {
        // опциональные методы, при старом SDK их может не быть
        openTelegramLink?: (url: string) => void;
        openLink?: (url: string) => void;
        CloudStorage?: {
          getItem: (key: string, cb: (err: string | null, value: string | null) => void) => void;
          setItem: (key: string, value: string, cb?: (err: string | null) => void) => void;
          removeItem: (key: string, cb?: (err: string | null) => void) => void;
        };
        initDataUnsafe?: {
          user?: {
            id: number;
            first_name?: string;
            last_name?: string;
            username?: string;
          };
        };
      };
    };
  }
}