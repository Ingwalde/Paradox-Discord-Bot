import os
from dotenv import load_dotenv
import sqlite3
import discord
from discord.ext import commands
from discord import ui
from flask import Flask
from threading import Thread
import asyncio
from pathlib import Path

app = Flask('')


@app.route('/')
def home():
    print("Ping received!")
    return "I'm alive!", 200


def run():

    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))


def keep_alive():
    t = Thread(target=run)
    t.start()


load_dotenv()
DB_DIR = "databases"
GAME_STYLES = {
    "eu4": {
        "name": "Europa Universalis 4",
        "color": 0x1f2b5d,
        "logo": "https://eu4.paradoxwikis.com/images/wiki.PNG"
    },
    "hoi4": {
        "name": "Hearts of Iron 4",
        "color": 0x1e321e,
        "logo": "https://hoi4.paradoxwikis.com/images/wiki.PNG?wordmark"
    },
    "stl": {
        "name": "Stellaris",
        "color": 0x6a4791,
        "logo": "https://stellaris.paradoxwikis.com/images/wiki.PNG"
    },
    "imp": {
        "name": "Imperator",
        "color": 0x660947,
        "logo": "https://imperator.paradoxwikis.com/images/wiki.PNG?wordmark"
    },
    "vic3": {
        "name": "Victoria 3",
        "color": 0x321a24,
        "logo": "https://vic3.paradoxwikis.com/images/wiki.PNG?wordmark"
    },
    "ck3": {
        "name": "Crusader Kings 3",
        "color": 0x780a02,
        "logo": "https://ck3.paradoxwikis.com/images/wiki.PNG?wordmark"
    },
}


def write_pid(filename="WIKI.pid"):
    with open(filename, "w") as f:
        f.write(str(os.getpid()))


write_pid()


def normalize(text: str) -> str:
    return text.lower().replace("_", " ").strip()


def db_path(game_key: str) -> str:
    return os.path.join(DB_DIR, f"{game_key}.db")


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="-", intents=intents, help_command=None)


def search_pages(game_key: str, query: str, limit=10):
    normalized_query = normalize(query)
    like_pattern = f"%{normalized_query}%"
    results = []

    with sqlite3.connect(db_path(game_key)) as conn:
        c = conn.cursor()

        # Точний збіг у Pages
        c.execute(
            """
            SELECT title, url, image_url FROM Pages
            WHERE LOWER(REPLACE(title, '_', ' ')) = ?
            LIMIT 1
        """, (normalized_query, ))
        row = c.fetchone()
        if row:
            results.append({
                "title": row[0],
                "url": row[1],
                "image_url": row[2]
            })

        # Якщо точного збігу немає або хочемо доповнити - шукаємо часткові збіги
        if len(results) < limit:
            c.execute(
                """
                SELECT title, url, image_url FROM Pages
                WHERE LOWER(REPLACE(title, '_', ' ')) LIKE ?
                ORDER BY title
                LIMIT ?
            """, (like_pattern, limit))
            rows = c.fetchall()
            for r in rows:
                # Уникнути дублювань, якщо точний збіг вже доданий
                if not any(x['title'] == r[0] for x in results):
                    results.append({
                        "title": r[0],
                        "url": r[1],
                        "image_url": r[2]
                    })
                    if len(results) >= limit:
                        break

        # Додатково можна аналогічно перевірити Redirects, якщо треба
    return results[:limit]


def search_similar(game_key: str, query: str, limit=10):
    normalized_query = normalize(query)
    matches = []

    with sqlite3.connect(db_path(game_key)) as conn:
        c = conn.cursor()

        # шукаємо в Pages
        c.execute(
            """
            SELECT title, url FROM Pages
            WHERE LOWER(REPLACE(title, '_', ' ')) LIKE ?
            ORDER BY title
            LIMIT ?
        """, (f"%{normalized_query}%", limit))
        pages = c.fetchall()

        # додаємо у matches словники з title і url
        for title, url in pages:
            matches.append({"title": title, "url": url})

        # якщо потрібно, можна також додати Redirects

    return matches[:limit]


class LinksView(ui.View):

    def __init__(self, pages):
        super().__init__(timeout=None)
        for p in pages[:5]:  # не більше 5 кнопок
            self.add_item(ui.Button(label=p['title'], url=p['url']))


async def send_wiki_embed(ctx, game_key, query):
    game = GAME_STYLES.get(game_key, {
        "name": "Paradox Wiki",
        "color": 0x95a5a6,
        "logo": None
    })
    pages = search_pages(game_key, query, limit=7)

    if pages:
        embed = discord.Embed(title=pages[0]["title"],
                              url=pages[0]["url"],
                              color=game["color"])
        embed.set_thumbnail(url=game["logo"])
        if pages[0].get("image_url"):
            embed.set_image(url=pages[0]["image_url"])

        # Формуємо текст зі списком посилань
        links_text = "\n".join(f"[{p['title']}]({p['url']})" for p in pages)
        embed.add_field(name="🔗 Посилання", value=links_text, inline=False)
        embed.set_footer(text=f"{game['name']} Wiki")
    else:
        embed = discord.Embed(
            title=f"За запитом '{query}' нічого не знайдено",
            description="Спробуйте інший запит або перевірте написання.",
            color=game["color"])
        if game["logo"]:
            embed.set_thumbnail(url=game["logo"])
        embed.set_footer(text=f"{game['name']} Wiki")

    msg = await ctx.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")

    await log_request(bot=ctx.bot,
                      ctx=ctx,
                      game_key=game_key,
                      query=query,
                      summary=bool(pages),
                      suggestions=[p["title"] for p in pages] if pages else [],
                      image_url=pages[0]["image_url"]
                      if pages and pages[0].get("image_url") else None)


async def log_request(bot, ctx, game_key, query, summary, suggestions,
                      image_url):
    game = GAME_STYLES[game_key]
    log_embed = discord.Embed(title="📄 Paradox Wiki Запит",
                              color=game["color"])
    log_embed.add_field(name="**User**",
                        value=f"<@{ctx.author.id}>",
                        inline=False)
    log_embed.add_field(name="**Request**",
                        value=f"`-{game_key} {query}`",
                        inline=False)
    log_embed.add_field(name="**Result**",
                        value=(f"Знайдено: {'так' if summary else 'ні'}\n"
                               f"Кількість результатів: {len(suggestions)}\n"
                               f"Картинка: {'так' if image_url else 'ні'}"),
                        inline=False)

    log_channel_id = int(os.getenv("LOG_CHANNEL_ID"))
    log_channel = bot.get_channel(log_channel_id)
    if log_channel:
        await log_channel.send(embed=log_embed)


# Команди для кожної гри
def register_game_commands():
    for key in GAME_STYLES:

        @bot.command(name=key)
        async def game_command(ctx, query: str, game_key=key):  # capture key
            await send_wiki_embed(ctx, game_key, query)


register_game_commands()

@bot.command(name="tools")
async def tools(ctx):
    await ctx.send("📤 Завантажте свій сейв-файл для PDX Tools протягом 60 секунд.")

    def check(m):
        return m.author == ctx.author and m.attachments and m.channel == ctx.channel

    try:
        msg = await bot.wait_for("message", timeout=60.0, check=check)
        attachment = msg.attachments[0]

        filepath = Path("temp") / attachment.filename
        filepath.parent.mkdir(parents=True, exist_ok=True)  # створення каталогу
        await attachment.save(fp=filepath)

        await ctx.send("⏳ Завантажую на https://pdx.tools ...")

        processed_url = f"https://pdx.tools/uploads/{attachment.filename}"

        conn = sqlite3.connect("pdx_tools.db")
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS Uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                filename TEXT,
                url TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("INSERT INTO Uploads (user_id, filename, url) VALUES (?, ?, ?)", (
            str(ctx.author.id),
            attachment.filename,
            processed_url
        ))
        conn.commit()
        conn.close()

        await ctx.send(f"✅ Завантажено: {processed_url}")
    except asyncio.TimeoutError:
        await ctx.send("⏱️ Час очікування вичерпано. Спробуйте ще раз.")

@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(
        title="Paradox Wiki Bot — Довідка",
        description=("Команди:\n"
                     "-`eu4 <запит>` — Europa Universalis 4\n"
                     "-`hoi4 <запит>` — Hearts of Iron 4\n"
                     "-`stl <запит>` — Stellaris\n"
                     "-`imp <запит>` — Imperator\n"
                     "-`vic3 <запит>` — Victoria 3\n"
                     "-`ck3 <запит>` — Crusader Kings 3\n\n"),
        color=0x8f1b1b)
    await ctx.send(embed=embed)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


keep_alive()
bot.run(os.getenv("TOKEN"))
