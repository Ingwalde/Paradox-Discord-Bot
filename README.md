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
cp .env.example .env    # заповніть TOKEN (обов'язково)
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
   тобто жодна команда не спрацює. Це найчастіша причина «бот онлайн, але мовчить».
4. Вкладка **OAuth2 → URL Generator**: scope `bot`, права *Send Messages*,
   *Embed Links*, *Add Reactions*, *Read Message History*. Відкрити згенероване
   посилання і додати бота на сервер.

Токен кладеться в `.env`, а не в код. `.env` уже в `.gitignore`.

### 2. `LOG_CHANNEL_ID` — канал для дзеркалення запитів (необов'язково)

Discord → **Налаштування → Додатково → Режим розробника** увімкнути →
правий клік на каналі → **Копіювати ID каналу**.

Без цієї змінної бот працює нормально, лише пише в лог попередження і не дзеркалить
запити в Discord.

### 3. `PDX_TOOLS_USER_ID` / `PDX_TOOLS_API_KEY` (необов'язково)

Потрібні лише для команди `-tools`. Реєстрація на [pdx.tools](https://pdx.tools)
(вхід через Steam) → сторінка акаунта → згенерувати API-ключ. Автентифікація —
HTTP basic auth: user id як логін, ключ як пароль.

⚠️ **Звірте ендпоінт** на [pdx.tools/docs/api](https://pdx.tools/docs/api/) і, якщо
він відрізняється від дефолтного, впишіть свій у `PDX_TOOLS_API_URL`. Те саме з
`PDX_TOOLS_SAVE_URL` — шаблон посилання на завантажений сейв. Ці два значення
винесені в `.env` саме тому, що їх не вдалося звірити з живою документацією під час
розробки; змінювати код для цього не потрібно.

Без ключів `-tools` чесно повідомляє, що завантаження не налаштоване.

### 4. API вікі — ключ не потрібен

MediaWiki Action API (`https://<game>.paradoxwikis.com/api.php`) анонімний.
Потрібен лише змістовний `User-Agent`. Бот наживо в нього не ходить — API
знадобиться, коли з'явиться скрипт оновлення баз (див. «Дані»).

## Якщо не працює

| Симптом | Причина |
|---|---|
| Бот онлайн, але не реагує на команди | Не увімкнено **MESSAGE CONTENT INTENT** |
| `TOKEN is not set` і вихід | Немає `.env` або порожній `TOKEN` |
| `Improper token has been passed` | Токен невірний — скиньте його в Developer Portal |
| `LOG_CHANNEL_ID is not set` (WARNING) | Норма, змінна необов'язкова |
| Бот не відповідає в конкретному каналі | Немає прав *Send Messages* / *Embed Links* |
| `-tools` каже «не налаштоване» | Немає `PDX_TOOLS_USER_ID` / `PDX_TOOLS_API_KEY` |
| `pdx.tools відхилив завантаження: HTTP 404` | Невірний `PDX_TOOLS_API_URL` |

Детальні логи — у `logs/bot.log` (рівень DEBUG, з ротацією); у консолі лише INFO.

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
