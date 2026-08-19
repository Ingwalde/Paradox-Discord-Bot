# Paradox Discord Bot

Discord-бот з українським інтерфейсом для пошуку сторінок Paradox-вікі
(контент вікі переважно англійський). Дані лежать локально в SQLite, тож пошук
не залежить від доступності вікі й відповідає за частки мілісекунди.

## Команди

| Команда | Гра |
|---|---|
| `-eu4 <запит>` | Europa Universalis 4 |
| `-hoi4 <запит>` | Hearts of Iron 4 |
| `-stl <запит>` | Stellaris |
| `-imp <запит>` | Imperator |
| `-vic3 <запит>` | Victoria 3 |
| `-ck3 <запит>` | Crusader Kings 3 |
| `-tools` | Завантажити сейв на [pdx.tools](https://pdx.tools) |
| `-help` | Довідка |

Запит може містити кілька слів: `-eu4 holy roman empire`.

## Запуск

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # заповніть TOKEN і LOG_CHANNEL_ID
python main.py
```

Бот піднімає keep-alive HTTP-ендпоінт на `PORT` (за замовчуванням 8080):
`GET /` і `GET /health` повертають `200 I'm alive!`.

## Конфігурація

Усі параметри читаються з `.env` — див. `.env.example`.

| Змінна | Обов'язкова | Опис |
|---|---|---|
| `TOKEN` | так | Токен Discord-бота |
| `LOG_CHANNEL_ID` | ні | Канал, куди дзеркаляться запити; без неї логування в Discord вимкнене |
| `DB_DIR` | ні | Каталог з `eu4.db`, `hoi4.db`, … (типово `databases`) |
| `PORT` | ні | Порт keep-alive (типово 8080) |
| `PDX_TOOLS_USER_ID`, `PDX_TOOLS_API_KEY` | ні | Ключі pdx.tools; без них `-tools` чесно каже, що аплоад не налаштовано |
| `PDX_TOOLS_API_URL`, `PDX_TOOLS_SAVE_URL` | ні | Ендпоінт і шаблон посилання pdx.tools |

Логи: консоль (INFO) і `logs/bot.log` (DEBUG, з ротацією).

## Дані

`databases/<game>.db` містять таблиці `Pages(title, url, image_url, lang)` та
`Redirects(redirect_title, redirect_url, target_page_url)`. Пошук зараз читає
лише `Pages`; `Redirects` — незадіяний резерв для покращення якості пошуку.

Бази статичні й лежать у репозиторії — скрипта оновлення поки немає. Вікі
працюють на MediaWiki (URL редиректів у базі мають вигляд
`index.php?title=X&redirect=no`), тож оновлення можна зібрати на Action API:
`api.php?action=query&list=allpages` для сторінок, `list=allredirects` для
редиректів, `generator=allpages&prop=pageimages` для картинок.

⚠️ Колонка `lang` недостовірна: значна частина рядків позначена як
`Українська`, хоча веде на англійські сторінки (`/Absolutism`, `/Aachen`).
Пошук її не використовує. Перезбирання через API з `prop=langlinks` це виправить.

## Відомі обмеження

- Немає ранжування результатів: часткові збіги сортуються за алфавітом.
- `Redirects` (кілька тисяч синонімів на гру) не використовується.
- Реакції ✅/❌ під відповіддю декоративні — обробника немає.
- Немає slash-команд; бот залежить від привілейованого інтенту `message_content`.
- Завантаження на pdx.tools реалізоване за документованим контрактом API, але не
  перевірене наскрізь — потрібен реальний API-ключ.
