# 🍺 Pivnitsa Pub

Краткое описание проекта.

## 🚀 Технологии

- Python
- FastAPI
- PostgreSQL
- Docker
- Redis

---

## 📥 Клонирование проекта

```bash
git clone https://github.com/Arybjan/pivnitsa_pub.git
cd pivnitsa_pub
```

---

## ⚙️ Установка

### Создание виртуального окружения

```bash
python -m venv .venv
```

Windows

```bash
.venv\Scripts\activate
```

Linux/macOS

```bash
source .venv/bin/activate
```

Установка зависимостей

```bash
pip install -r requirements.txt
```

---

## 🔐 Настройка окружения

Создать файл

```
.env
```

Пример

```env
DEBUG=True

SECRET_KEY=

DB_NAME=
DB_USER=
DB_PASSWORD=
DB_HOST=
DB_PORT=

REDIS_HOST=
REDIS_PORT=
```

---

## 🗄 Миграции

```bash
alembic upgrade head
```

---

## ▶ Запуск проекта

```bash
uvicorn app.main:app --reload
```

---

## 🐳 Запуск через Docker

```bash
docker compose up --build
```

Остановка

```bash
docker compose down
```

---

## 📁 Структура проекта

```
backend/
frontend/
docker/
nginx/
app/
...
```

---

## 🌿 Git Flow

Создать ветку

```bash
git checkout -b feature/login
```

Перед отправкой

```bash
git pull origin develop
git push origin feature/login
```

Создать Pull Request.

---

## 📝 Правила разработки

- Не коммитить `.env`
- Перед коммитом запускать тесты
- Использовать Black
- Использовать Ruff/Flake8
- Именование веток:
  - feature/*
  - fix/*
  - hotfix/*
  - refactor/*

---

## 🤝 Участие в разработке

1. Создать ветку
2. Сделать изменения
3. Проверить код
4. Commit
5. Push
6. Pull Request
