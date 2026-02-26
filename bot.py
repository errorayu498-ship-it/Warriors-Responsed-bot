import discord
import os
import sqlite3
import time
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
PRIVATE_CHANNEL_ID = int(os.getenv("PRIVATE_CHANNEL_ID"))
PUBLIC_CHANNEL_ID = int(os.getenv("PUBLIC_CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True

bot = discord.Client(intents=intents)

# ================= DATABASE =================

db = sqlite3.connect("database.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS message_map(
private_id INTEGER PRIMARY KEY,
public_id INTEGER
)
""")
db.commit()

def save_mapping(private_id, public_id):
    cursor.execute(
        "INSERT OR REPLACE INTO message_map VALUES (?,?)",
        (private_id, public_id)
    )
    db.commit()

def get_public_id(private_id):
    cursor.execute(
        "SELECT public_id FROM message_map WHERE private_id=?",
        (private_id,))
    data = cursor.fetchone()
    return data[0] if data else None

def delete_mapping(private_id):
    cursor.execute(
        "DELETE FROM message_map WHERE private_id=?",
        (private_id,))
    db.commit()

# ================= ANTI SPAM =================

user_cooldowns = {}
SPAM_LIMIT = 3        # messages
TIME_WINDOW = 5       # seconds

def is_spamming(user_id):
    now = time.time()

    if user_id not in user_cooldowns:
        user_cooldowns[user_id] = []

    user_cooldowns[user_id].append(now)

    # remove old timestamps
    user_cooldowns[user_id] = [
        t for t in user_cooldowns[user_id]
        if now - t < TIME_WINDOW
    ]

    return len(user_cooldowns[user_id]) > SPAM_LIMIT

# ================= READY =================

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print("🔥 Forward Bot V4 Active")

# ================= SAFE SEND =================

async def safe_send(channel, **kwargs):
    try:
        return await channel.send(**kwargs)
    except Exception as e:
        print(f"Send Error: {e}")
        return None

# ================= FORWARD =================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if message.channel.id != PRIVATE_CHANNEL_ID:
        return

    # Anti Spam
    if is_spamming(message.author.id):
        print(f"🚫 Spam Blocked: {message.author}")
        return

    public_channel = bot.get_channel(PUBLIC_CHANNEL_ID)
    if not public_channel:
        return

    try:
        sent_msg = None

        if message.content:
            sent_msg = await safe_send(
                public_channel,
                content=message.content
            )

        if message.attachments:
            files = [await a.to_file() for a in message.attachments]
            sent_msg = await safe_send(public_channel, files=files)

        if message.embeds:
            for embed in message.embeds:
                sent_msg = await safe_send(public_channel, embed=embed)

        if sent_msg:
            save_mapping(message.id, sent_msg.id)

        print("✅ Forwarded")

    except Exception as e:
        print(f"Forward Error: {e}")

# ================= EDIT SYNC =================

@bot.event
async def on_message_edit(before, after):

    if after.author.bot:
        return

    if after.channel.id != PRIVATE_CHANNEL_ID:
        return

    public_id = get_public_id(before.id)
    if not public_id:
        return

    public_channel = bot.get_channel(PUBLIC_CHANNEL_ID)

    try:
        public_msg = await public_channel.fetch_message(public_id)
        await public_msg.edit(content=after.content)
        print("🔁 Edit Synced")

    except Exception as e:
        print(f"Edit Error: {e}")

# ================= DELETE SYNC =================

@bot.event
async def on_message_delete(message):

    if message.channel.id != PRIVATE_CHANNEL_ID:
        return

    public_id = get_public_id(message.id)
    if not public_id:
        return

    public_channel = bot.get_channel(PUBLIC_CHANNEL_ID)

    try:
        public_msg = await public_channel.fetch_message(public_id)
        await public_msg.delete()

        delete_mapping(message.id)

        print("🗑 Delete Synced")

    except discord.NotFound:
        delete_mapping(message.id)
    except Exception as e:
        print(f"Delete Error: {e}")

bot.run(TOKEN)
