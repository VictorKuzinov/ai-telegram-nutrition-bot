# Nutriciolog Bot

Telegram-бот нутрициолога на Python и Aiogram 3.

## Возможности

- Расчёт BMR (базового обмена веществ)
- Расчёт суточной калорийности
- Расчёт БЖУ
- Выбор активности и цели через Telegram-кнопки
- FSM-диалог пользователя
- Валидация ввода
- Хранение профилей пользователей в SQLite
- Подготовка к интеграции AI-моделей и анализа питания

---

## Стек

- Python 3.12+
- Aiogram 3
- SQLAlchemy
- SQLite
- Pydantic
- Requests
- dotenv

---

## Структура проекта

```text
nutriciolog_bot/
├── handlers/
├── db/
├── nutrition/
├── ai/
├── data/
├── certs/
├── bot.py
├── keyboards.py
├── states.py
├── validators.py
├── requirements.txt
└── .env.example
```

---

## Установка

### 1. Клонирование проекта

```bash
git clone <repo_url>
cd nutriciolog_bot
```

### 2. Создание виртуального окружения

```bash
python -m venv .venv
```

### 3. Активация окружения

Windows:

```bash
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

### 4. Установка зависимостей

```bash
pip install -r requirements.txt
```

---

## Настройка

Создайте файл `.env`

Пример:

```env
TELEGRAM_BOT_TOKEN=your_token
```

---

## Запуск

```bash
python bot.py
```

---

## Текущий функционал

Бот умеет:

- Запрашивать:
  - пол
  - возраст
  - рост
  - вес
  - уровень активности
  - цель

- Рассчитывать:
  - BMR
  - суточную калорийность
  - БЖУ

---

## Планы развития

- Хранение истории расчётов
- AI-анализ питания
- Анализ продуктов по фото
- Интеграция USDA
- Генерация меню
- PostgreSQL
- Docker
- Alembic
- Админ-панель

---

## Автор

Виктор Кузинов
