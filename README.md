# Ката #03 — База данных-сан

## Легенда

Калькулятор повзрослел — теперь ему нужна память.  
Сейчас история вычислений живёт внутри контейнера и исчезает при каждом перезапуске.  
Твоя задача — подключить PostgreSQL так, чтобы данные переживали любой рестарт.

---

## Что дано

```
app/                 — калькулятор, переписанный на PostgreSQL
.env.example         — пример переменных окружения
docker-compose.yml   — сервис calculator уже описан, db — твоя задача
```

Приложение читает подключение к базе из переменных окружения:

| Переменная | Назначение |
|------------|------------|
| `DB_HOST` | адрес сервера базы данных |
| `DB_PORT` | порт (по умолчанию 5432) |
| `DB_NAME` | имя базы данных |
| `DB_USER` | пользователь |
| `DB_PASSWORD` | пароль |

Все нужные значения есть в `.env.example`.

---

## Задание

### Шаг 1 — Создай `.env`

```bash
cp .env.example .env
```

> `.env` уже в `.gitignore` — секреты в репо не попадут.

### Шаг 2 — Допиши `docker-compose.yml`

Открой файл — сервис `calculator` уже готов, внутри два TODO.  
Тебе нужно:

1. Описать сервис `db` с образом `postgres:16-alpine`
2. Передать ему переменные окружения из `.env`
3. Подключить именованный volume чтобы данные сохранялись на диске

Документация которая поможет:
- [Образ postgres на Docker Hub](https://hub.docker.com/_/postgres) — раздел «Environment Variables»
- [Volumes в Compose](https://docs.docker.com/compose/how-tos/volumes-and-storage/)

### Шаг 3 — Подними стек

```bash
docker-compose up --build
```

Оба сервиса должны подняться:

```
calculator  | INFO:     Application startup complete.
db          | database system is ready to accept connections
```

Проверь что API отвечает:

```
http://localhost:8088/docs
```

### Шаг 4 — Проверь персистентность

Это главная проверка этой каты. Выполни по порядку:

```bash
# 1. Создай несколько вычислений через /docs или curl

# 2. Останови стек
docker-compose down

# 3. Подними снова
docker-compose up

# 4. Проверь историю
GET http://localhost:8088/api/v1/calculations
```

Если данные на месте — ката пройдена.

### Шаг 5 — Посмотри на данные в базе напрямую

Подключись к postgres внутри контейнера и посмотри что там лежит:

```bash
docker-compose exec db psql -U calculator_user -d calculator
```

Внутри psql:

```sql
SELECT * FROM calculations;
\q
```

---

*Данные не должны умирать вместе с контейнером.*
