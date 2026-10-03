from typing import Any


TEMPLATES = {
    "event_published": {
        "push_title": "Анонс: {title}",
        "push_message": "Мероприятие «{title}» запланировано на {date}. Бронируйте столики заранее!",
        "sms": "Pivnitsa: {title} {date}. Bronirovanie stolov na saite!",
    },
    "event_cancelled": {
        "push_title": "Отмена мероприятия: {title}",
        "push_message": "К сожалению, мероприятие «{title}» было отменено.",
        "sms": "Pivnitsa: Meropriyatie «{title}» otmeneno.",
    },
    "event_updated": {
        "push_title": "Обновление мероприятия: {title}",
        "push_message": "Информация о мероприятии «{title}» была обновлена. Проверьте детали в афише.",
        "sms": "Pivnitsa: Izmeneniya v «{title}». Detali na saite.",
    },
    "booking_created": {
        "push_title": "Бронь столика создана",
        "push_message": "Столик №{table_number} временно забронирован. Пожалуйста, оплатите бронь в течение 10 минут.",
        "sms": "Pivnitsa: Stol #{table_number} zabronirovan. Oplata v techenie 10 min.",
    },
    "booking_confirmed": {
        "push_title": "Бронь подтверждена",
        "push_message": "Ваша бронь столика №{table_number} успешно подтверждена!",
        "sms": "Pivnitsa: Vasha bron stola #{table_number} podtverzhdena! Zhdem vas!",
    },
    "booking_cancelled": {
        "push_title": "Бронь отменена",
        "push_message": "Бронь столика №{table_number} была отменена.",
        "sms": "Pivnitsa: Bron stola #{table_number} otmenena.",
    },
    "booking_expired": {
        "push_title": "Время брони истекло",
        "push_message": "Время ожидания оплаты для столика №{table_number} истекло, бронь аннулирована.",
        "sms": "Pivnitsa: Vremya oplaty stola #{table_number} isteklo. Bron snyata.",
    },
}


def render_notification(template_key: str, **kwargs: Any) -> tuple[str, str]:
    tmpl = TEMPLATES.get(template_key)
    if not tmpl:
        return kwargs.get("title", "Уведомление"), kwargs.get("message", "")
    
    clean_kwargs = {k: ("" if v is None else v) for k, v in kwargs.items()}
    try:
        title = tmpl["push_title"].format(**clean_kwargs)
    except KeyError:
        title = kwargs.get("title", "Уведомление")
        
    try:
        message = tmpl["push_message"].format(**clean_kwargs)
    except KeyError:
        message = kwargs.get("message", "")
        
    return title, message


def render_sms(template_key: str, **kwargs: Any) -> str | None:
    tmpl = TEMPLATES.get(template_key)
    if not tmpl or "sms" not in tmpl:
        return None
    clean_kwargs = {k: ("" if v is None else v) for k, v in kwargs.items()}
    try:
        return tmpl["sms"].format(**clean_kwargs)
    except KeyError:
        return None
