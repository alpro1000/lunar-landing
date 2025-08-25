# Lunar Dream Calendar (Graphite Night)

Статический сайт: лунный календарь снов + современный сонник + клиентский разбор сна.

## Быстрый старт (GitHub Pages)
1. Склонируйте репозиторий или загрузите файлы.
2. Убедитесь, что есть `data/dreams_curated.json` (можно с примерами).
3. Включите Pages: Settings → Pages → Branch: `main` → `/ (root)`.
4. Откройте: `https://<username>.github.io/lunar-landing/`.

## Структура
- `index.html` — разметка.
- `styles/*` — тема Graphite Night.
- `scripts/calendar.js` — календарь, луна, локали.
- `scripts/dreambook.js` — поиск по соннику и «Разбор сна».
- `data/dreams_curated.json` — набор символов (обновляйте ETL-скриптами).

## Настройка
- Язык берётся из браузера, можно переключить селектором.
- Часовой пояс — авто/список.
- Иконка луны — монохромный SVG-серп, фаза рассчитывается приближённо.

## Данные
`data/dreams_curated.json` можно обновлять вручную или через CI.
