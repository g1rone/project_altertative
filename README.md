# Pax 1933 Starter

Минимальный стартовый каркас для браузерной grand-strategy песочницы:

- Frontend: React + TypeScript + Vite + MapLibre GL JS
- Backend: Python + FastAPI
- Карта: пока demo GeoJSON с упрощёнными полигонами Европы
- Следующий шаг: заменить demo-карту на исторические границы CShapes 2.0 для 1933 года

## Запуск backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Backend будет на:

```text
http://127.0.0.1:8000
```

Проверка:

```text
http://127.0.0.1:8000/api/health
```

## Запуск frontend

В другом терминале:

```bash
cd frontend
npm install
npm run dev
```

Frontend будет на адресе, который покажет Vite, обычно:

```text
http://localhost:5173
```

## Что уже работает

1. React загружает GeoJSON-карту с backend.
2. MapLibre рисует страны.
3. Клик по стране выбирает её.
4. Справа показывается карточка страны.
5. Можно отправить действие.
6. Backend применяет fake-эффекты.
7. Frontend обновляет карточку и журнал событий.

## Важно

Файл `backend/data/europe_1933_demo.geojson` — не настоящая карта 1933 года, а грубый demo-слой, чтобы интерфейс уже работал.
Настоящую карту будем готовить из CShapes 2.0 отдельным скриптом.
