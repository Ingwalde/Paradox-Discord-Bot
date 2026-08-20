# Paradox Discord Bot

[![CI](https://github.com/Ingwalde/Paradox-Discord-Bot/actions/workflows/ci.yml/badge.svg)](https://github.com/Ingwalde/Paradox-Discord-Bot/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![discord.py](https://img.shields.io/badge/discord.py-2.x-5865F2?logo=discord&logoColor=white)
![mypy](https://img.shields.io/badge/mypy-checked-2A6DB2)
![Coverage](https://img.shields.io/badge/coverage-46%25*-yellow)
[![License: MIT](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

Discord-бот з українським інтерфейсом для пошуку сторінок Paradox-вікі
(контент вікі переважно англійський). Дані лежать локально в SQLite, тож пошук
не залежить від доступності вікі й відповідає за частки мілісекунди.

```text
Discord (prefix + admin slash) → paradox_bot/bot.py → paradox_bot/search.py ─┐
                                          │                                   ├─ databases/<game>.db (SQLite)
                                          └→ paradox_bot/pdx_tools.py ────────┘         ↑
                                                     │                    scripts/import_wiki.py
                                                     └→ https://pdx.tools/api/saves     (MediaWiki API)
```

## Architecture

Один пакет `paradox_bot/`, розділений за відповідальністю, `main.py` —
тонкий entrypoint (TOKEN, PID, запуск).

| Модуль | Відповідає за |
|---|---|
| `config.py` | `Settings` (типізований dataclass, читається з env один раз) + логування |
| `games.py` | `GameInfo`/`GAMES` — єдине джерело правди про підтримувані ігри (ключ команди, стиль, wiki-піддомен) |
| `search.py` | SQLite-пошук: `Pages` + `Redirects`, ранжування, fuzzy-підказки, випадкова сторінка |
| `pdx_tools.py` | Аплоад сейву на pdx.tools, дедуп повторних завантажень |
| `feedback.py` | ✅/❌ голоси під результатами (контекст повідомлення + збереження) |
| `stats.py` | Лог пошукових запитів для `-trending` |
| `bot.py` | `ParadoxBot`, динамічна реєстрація команд по іграх, embed-логіка, event-хендлери |
| `cogs/` | Cog-и для статичних команд: `tools`, `help`, `extras` (`-random`/`-trending`/факт дня), `admin` (slash) |
| `web.py` | Keep-alive HTTP-ендпоінт (Flask) |

Динамічні по-ігрові команди (`-eu4`, `-eu5`, …) реєструються напряму на боті,
не через Cog — вони породжуються цик­лом по `GAMES`, а не декоратором, тож
заганяти їх у Cog-стиль додало б тертя без користі.

## Команди

| Команда | Опис |
|---|---|
| `-eu4 <запит>`, `-eu5`, `-hoi4`, `-stl`, `-imp`, `-vic3`, `-ck3` | Пошук у вікі гри (кілька слів дозволено) |
| `-random <гра>` | Випадкова стаття |
| `-trending <гра>` | Топ запитів за останній тиждень |
| `-tools` | Завантажити сейв на [pdx.tools](https://pdx.tools) |
| `-help` | Довідка |
| `/admin status` | Здоров'я бота, статистика БД по іграх (лише для адміністраторів сервера) |
| `/admin feedback` | Останні ✅/❌ голоси (лише для адміністраторів сервера) |

## Запуск

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pre-commit install               # опційно, але рекомендовано
cp .env.example .env             # заповніть TOKEN (обов'язково)
python main.py
```

В консолі має з'явитися `Logged in as <ім'я бота>`. Далі в Discord: `-help`,
потім `-eu4 holy roman empire`.

Бот піднімає keep-alive HTTP-ендпоінт на `PORT` (за замовчуванням 8080):
`GET /` і `GET /health` повертають `200 I'm alive!`.

## Де взяти токени і ключі

### 1. `TOKEN` — токен Discord-бота (обов'язково)

1. [discord.com/developers/applications](https://discord.com/developers/applications)
   → **New Application**.
2. Вкладка **Bot** → **Reset Token** → скопіювати. Токен показується **один раз**;
   якщо загубили — треба скидати заново.
3. Там же, **Privileged Gateway Intents** → увімкнути **MESSAGE CONTENT INTENT**.
   Без нього бот під'єднається і буде онлайн, але **не бачитиме тексту повідомлень**,
   тобто жодна префіксна команда не спрацює (`-eu4`, `-tools`, ...). Це
   найчастіша причина «бот онлайн, але мовчить». Свідомо не прибрано —
   `/admin` наразі єдина slash-команда, решта лишається на префіксах.
4. Вкладка **OAuth2 → URL Generator**: scope `bot` і `applications.commands`
   (для `/admin`), права *Send Messages*, *Embed Links*, *Add Reactions*,
   *Read Message History*. Відкрити згенероване посилання і додати бота на
   сервер.

Токен кладеться в `.env`, а не в код. `.env` уже в `.gitignore`.

### 2. `LOG_CHANNEL_ID` — канал для дзеркалення запитів (необов'язково)

Discord → **Налаштування → Додатково → Режим розробника** увімкнути →
правий клік на каналі → **Копіювати ID каналу**.

Без цієї змінної бот працює нормально, лише пише в лог попередження і не дзеркалить
запити в Discord.

### 3. `PDX_TOOLS_USER_ID` / `PDX_TOOLS_API_KEY` (необов'язково)

Потрібні лише для команди `-tools`. Реєстрація на [pdx.tools](https://pdx.tools)
(вхід через Steam) → сторінка акаунта → згенерувати API-ключ. Автентифікація —
HTTP basic auth: user id як логін, ключ як пароль. Ендпоінт, заголовки й формат
відповіді звірені з [pdx.tools/docs/api](https://pdx.tools/docs/api/) і перевірені
наживо (успішний аплоад і коректна обробка дубліката).

Без ключів `-tools` чесно повідомляє, що завантаження не налаштоване.

### 4. `DEV_GUILD_ID` (необов'язково, для розробки)

ID тестового сервера — з ним `/admin`-команди синхронізуються миттєво.
Без нього синхронізація глобальна і може зайняти до години.

### 5. `DAILY_FACT_CHANNEL_ID` (необов'язково)

Канал, куди раз на день (12:00 UTC) постить випадкову статтю з випадкової гри.
Порожньо — функція вимкнена.

### 6. API вікі — ключ не потрібен

MediaWiki Action API (`https://<game>.paradoxwikis.com/api.php`) анонімний.
`scripts/import_wiki.py` ним і користується для наповнення `databases/<game>.db`
(`python scripts/import_wiki.py eu5`, реюзабельно для будь-якої гри з
`paradox_bot/games.py`).

## Якщо не працює

| Симптом | Причина |
|---|---|
| Бот онлайн, але не реагує на префіксні команди | Не увімкнено **MESSAGE CONTENT INTENT** |
| `TOKEN is not set` і вихід | Немає `.env` або порожній `TOKEN` |
| `Improper token has been passed` | Токен невірний — скиньте його в Developer Portal |
| `/admin` не з'являється в Discord | Глобальна синхронізація до години; задайте `DEV_GUILD_ID` для миттєвої |
| `/admin` є, але недоступна | Потрібні права адміністратора на сервері |
| Бот не відповідає в конкретному каналі | Немає прав *Send Messages* / *Embed Links* |
| `-tools` каже «не налаштоване» | Немає `PDX_TOOLS_USER_ID` / `PDX_TOOLS_API_KEY` |

Детальні логи — у `logs/bot.log` (рівень DEBUG, з ротацією); у консолі лише INFO.

## Конфігурація

Усі параметри читаються з `.env` в `Settings.from_env()` — див. `.env.example`.

| Змінна | Обов'язкова | Опис |
|---|---|---|
| `TOKEN` | так | Токен Discord-бота |
| `LOG_CHANNEL_ID` | ні | Канал, куди дзеркаляться запити |
| `DB_DIR` | ні | Каталог з `eu4.db`, `eu5.db`, … (типово `databases`) |
| `PORT` | ні | Порт keep-alive (типово 8080) |
| `DEV_GUILD_ID` | ні | Сервер для миттєвої синхронізації `/admin` |
| `DAILY_FACT_CHANNEL_ID` | ні | Канал для щоденного авто-поста (12:00 UTC) |
| `PDX_TOOLS_USER_ID`, `PDX_TOOLS_API_KEY` | ні | Ключі pdx.tools |
| `PDX_TOOLS_API_URL`, `PDX_TOOLS_SAVE_URL` | ні | Ендпоінт і шаблон посилання pdx.tools |

## Дані

`databases/<game>.db`: `Pages(title, url, image_url, lang)` та
`Redirects(redirect_title, redirect_url, target_page_url)` — обидві таблиці
беруть участь у пошуку (ранжування: точний збіг → з початку → входження
всередині), плюс fuzzy-підказки на порожньому результаті.

Наповнюються через `python scripts/import_wiki.py <гра>` (MediaWiki Action
API, без ключа). Безпечно перезапускати — таблиці перебудовуються з нуля.

Пошук сканує таблиці цілком: `LIKE '%запит%'` має провідний `%`, який жоден
B-tree індекс обслужити не може. На ~2000 рядків це ≈3 мс у робочому потоці.
Плани щодо індексованої нормалізованої колонки — у [ROADMAP.md](ROADMAP.md).

⚠️ Колонка `lang` недостовірна (значна частина рядків позначена як
«Українська», хоча веде на англійські сторінки) і пошуком не читається.

## Тестування та якість

```bash
ruff check main.py paradox_bot/ tests/ scripts/
mypy
pytest -q --cov=paradox_bot --cov-report=term-missing
```

79 тестів проти чистих функцій (`search.py`, `pdx_tools.py`, `feedback.py`,
`stats.py`, `config.py`, плюс `build_links_field` та ліміти команд у `bot.py`)
і проти реального локального `aiohttp`-сервера для `-tools`-аплоаду.
\* Coverage-бейдж (46%) — по всьому пакету; більшість Discord-специфічного
шару (`cogs/`, `web.py`, event-хендлери в `bot.py`) свідомо не тестується
(мокати Discord — дорого й крихко), а логіка під ним покрита на 91–100%:

| Модуль | Покриття |
|---|---|
| `config.py`, `feedback.py`, `games.py`, `stats.py` | 100% |
| `search.py` | 96% |
| `pdx_tools.py` | 91% |
| `bot.py` | 30% (чисті хелпери; event-хендлери й Discord-виклики — ні) |
| `cogs/*`, `web.py` | 0% (навмисно) |

pre-commit (`pre-commit install`): ruff, mypy, `detect-private-key`,
`check-added-large-files`.

## Деплой на Replit

⚠️ **Тільки Reserved VM.** Бот тримає постійне gateway-з'єднання з Discord і
**ніколи не отримує вхідних HTTP-запитів**, тому Autoscale-деплой
(`deploymentTarget = "cloudrun"`) згортається до нуля і бот іде офлайн.
Always-On Replit прибрав у січні 2024, тож зарезервований інстанс — єдиний
спосіб лишатися підключеним.

У Deployments оберіть **Reserved VM** і дайте Replit самому переписати
`deploymentTarget` у `.replit` — не редагуйте це значення вручну.

Змінні з `.env` задаються в розділі **Secrets**, а не файлом: `.env` у
`.gitignore` і в деплой не потрапляє.

Keep-alive ендпоінт (`GET /`, `GET /health` на `PORT`) на Reserved VM для
підтримки життя не потрібен — лишається як health-check.

## Відомі обмеження

- Префіксні команди (`-eu4`, `-tools`, …) лишаються на `message_content` —
  привілейованому інтенті, який після 100 гільдій потребує верифікації
  Discord. Свідомий вибір: `/admin` — єдина slash-команда, решта інтерфейсу
  не мігрувала (див. CHANGELOG 0.1.0).
- Порівняння двох сейвів на pdx.tools не реалізоване — офіційний API цього
  не підтримує (документація прямо радить сторонній сервіс для такого
  сценарію).
- Колонка `lang` у базах недостовірна й не використовується.
