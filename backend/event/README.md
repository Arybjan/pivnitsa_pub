# Event Service

## Запуск

Скопируйте `.env.example` в `.env` и установите общий с Auth секрет `JWT_SECRET`.
Поддерживается также прежнее имя `JWT_SECRET_KEY`; при наличии обоих используется `JWT_SECRET`.

```sh
docker compose up --build
```

Контейнер применяет `alembic upgrade head` перед запуском приложения. Сервис доступен
на `http://localhost:8002`, Swagger — `/docs`. Внутри контейнера порт остаётся 8001.
Хост-порты PostgreSQL, Redis и RabbitMQ: 5433, 6380, 5673; RabbitMQ management: 15673.
Порты можно изменить через переменные `EVENT_*_PORT` в `.env.example`.
Этот Compose запускает собственный RabbitMQ: при интеграции Notifications должен
подключаться к тому же брокеру; `RABBITMQ_URL` можно переопределить в общей конфигурации.

Для прямого запуска, включая Windows:

```sh
python -m pip install -r requirements.txt
python -m alembic upgrade head
python -m uvicorn app.main:app --host 0.0.0.0 --port 8002
```

БД, Redis и RabbitMQ должны быть доступны по адресам из `.env`.

## API и Auth

- `GET /api/v1/events` — опубликованные будущие мероприятия.
- `GET /api/v1/events/all` — административный список, со статическим маршрутом перед ID.
- Неопубликованные карточки доступны только активным `admin`/`owner`; гостям возвращается 404.
- `POST /api/v1/events` создаёт `DRAFT`; `PATCH /{id}` изменяет поля.
- `POST /{id}/publish` переводит `DRAFT` в `PUBLISHED`, `unpublish` возвращает в `DRAFT`.
- `cancel` устанавливает `CANCELLED`; PATCH с `{"status":"FINISHED"}` завершает опубликованное мероприятие.
- Повторный publish для `PUBLISHED` возвращает текущую карточку и не создаёт сообщения.
- PUT сохранён как deprecated alias PATCH.

Ответы и OpenAPI используют `starts_at`, `ends_at` и статусы
`DRAFT`, `PUBLISHED`, `CANCELLED`, `FINISHED`. Старые имена входных дат
`start_datetime`/`end_datetime` и нижний регистр статусов принимаются.
Даты без timezone интерпретируются как UTC; даты с timezone нормализуются в UTC.
В PostgreSQL даты хранятся как `TIMESTAMP WITH TIME ZONE`, автор — `UUID`.

Принятый JWT-контракт: UUID в `sub`, обязательный `exp`, `type="access"`
или `token_type="access"`, `is_active=true` как boolean, роль в `role`.
Если оба claims типа присутствуют, оба должны быть `access`.
Refresh, истёкший и некорректный токены получают 401, неактивный пользователь — 403.
Точный внешний контракт Auth в этом репозитории отсутствует; указанные имена claims
нужно сверить с Auth. Активность проверяется по подписанному claim; изменение
пользователя после выдачи JWT потребует механизма отзыва/проверки со стороны Auth.

Readiness возвращает 200 только при доступных БД и Redis, иначе 503.

## Миграция существующей БД

Пустая БД создаётся автоматически миграциями. Таблица прежней версии с `created_by bigint`
может быть принята первой миграцией. Для заполненной БД перед второй миграцией нужна
реальная таблица соответствий авторов из Auth:

```sql
CREATE TABLE event_author_map (
    legacy_id bigint PRIMARY KEY,
    user_id uuid NOT NULL
);
-- INSERT реальных соответствий, затем alembic upgrade head
```

Без полного соответствия миграция прерывается, сохраняя данные. Старые даты без
часового пояса считаются UTC; если они записывались в локальном времени, необходимо
скорректировать преобразование перед миграцией. ARCHIVED становится FINISHED.
Обратное преобразование UUID в integer не поддерживается.

## Доставка уведомлений и оставшаяся интеграция Notifications

Переход статуса и сообщение сохраняются одной транзакцией в `event_outbox`.
Фоновый обработчик отправляет сообщения каждые пять секунд в durable topic exchange
`events_exchange`, routing key `event.published` или `event.cancelled`.
Используются persistent messages, publisher confirms и mandatory routing;
сбой брокера или отсутствие binding оставляют сообщение для повторной отправки.
При `send_notifications=false` публикация не создаёт сообщение уведомления.

Тело publish может содержать `recipient_ids` со списком UUID:

```json
{"send_notifications": true, "recipient_ids": ["6be6b360-313a-4f67-bafd-9dd1bdbd7c31"]}
```

Повторы ID удаляются. Без списка payload задаёт аудиторию всех активных гостей:

```json
{
  "message_id": "unique-publication-uuid",
  "event_id": 1,
  "title": "Concert",
  "starts_at": "2030-08-20T18:00:00+00:00",
  "start_datetime": "2030-08-20T18:00:00+00:00",
  "send_notifications": true,
  "recipient_ids": null,
  "audience": {"role": "guest", "is_active": true},
  "timestamp": "2026-10-04T00:00:00+00:00"
}
```

`message_id` совпадает с AMQP message_id и сохраняется при повторной доставке.
После unpublish новая публикация получает новый ID.

Кода Notifications и API получения гостей здесь нет. Для завершения US-28 consumer должен:

1. Привязать свою durable очередь к `events_exchange` с нужными routing keys.
2. Использовать явные `recipient_ids` либо разрешать `audience` через согласованный API Auth.
   Удалить fallback на `EVENT_NOTIFICATION_DEFAULT_USER_ID=1`.
3. В одной транзакции создавать уведомления с уникальностью `(message_id, recipient_id)`.
4. Подтверждать AMQP-сообщение после commit; при redelivery повтор не создаёт запись.

Outbox обеспечивает доставку как минимум один раз. Сбой после подтверждения брокера
до commit outbox может повторить сообщение; полная защита от дублей зависит от пункта 3.
Изменения consumer и интеграционная проверка всей цепочки остаются вне этого репозитория.

## Проверки

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

SQLite покрывает API, Auth, миграции пустой БД и retries outbox.
Чтобы проверить блокировки на PostgreSQL, задайте `EVENT_TEST_DATABASE_URL` для
отдельной тестовой БД (для теста миграции нужен CREATE DATABASE). Тесты очищают `events` и `event_outbox` в этой БД:

```sh
EVENT_TEST_DATABASE_URL=postgresql+asyncpg://user:password@localhost/test_events python -m pytest -q
```
