import discord
from discord import ui, app_commands
import asyncio
import aiosqlite
import os
import pytz
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

TOKEN=os.getenv("TOKEN")
PRIVATE_CHANNEL_ID=int(os.getenv("PRIVATE_CHANNEL_ID"))
PUBLIC_CHANNEL_ID=int(os.getenv("PUBLIC_CHANNEL_ID"))
LOG_CHANNEL_ID=int(os.getenv("LOG_CHANNEL_ID"))

PKT = pytz.timezone("Asia/Karachi")

intents = discord.Intents.default()
intents.message_content=True

class ForwardBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

bot = ForwardBot()

# ================= DATABASE =================

async def setup_db():
    async with aiosqlite.connect("database.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS scheduled(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            send_time TEXT
        )
        """)
        await db.commit()

# ================= LOG SYSTEM =================

async def log(text):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(f"📜 {text}")

# ================= SCHEDULER =================

async def scheduler():
    await bot.wait_until_ready()

    while True:
        async with aiosqlite.connect("database.db") as db:
            async with db.execute("SELECT id,content,send_time FROM scheduled") as cur:
                rows = await cur.fetchall()

                for sid,content,time_str in rows:
                    send_time=datetime.fromisoformat(time_str)

                    if datetime.utcnow()>=send_time:
                        ch=bot.get_channel(PUBLIC_CHANNEL_ID)
                        if ch:
                            await ch.send(content)
                            await log(f"Scheduled Message Sent (ID:{sid})")

                        await db.execute("DELETE FROM scheduled WHERE id=?",(sid,))
                        await db.commit()

        await asyncio.sleep(10)

# ================= MODAL =================

class ScheduleModal(ui.Modal,title="Set Pakistan Time"):
    time=ui.TextInput(label="PKT Time",placeholder="2026-03-01 22:30")

    def __init__(self,msg):
        super().__init__()
        self.msg=msg

    async def on_submit(self,interaction:discord.Interaction):
        try:
            pkt_time=PKT.localize(
                datetime.strptime(str(self.time),"%Y-%m-%d %H:%M")
            )
            utc_time=pkt_time.astimezone(pytz.utc)

            async with aiosqlite.connect("database.db") as db:
                await db.execute(
                    "INSERT INTO scheduled(content,send_time) VALUES(?,?)",
                    (self.msg.content,utc_time.isoformat())
                )
                await db.commit()

            await interaction.response.send_message(
                "✅ Message Scheduled (PKT Saved)",
                ephemeral=True
            )

            await log("New Scheduled Message Added")

        except:
            await interaction.response.send_message(
                "❌ Invalid Time Format",
                ephemeral=True
            )

# ================= BUTTON VIEW =================

class ForwardView(ui.View):
    def __init__(self,msg):
        super().__init__(timeout=None)
        self.msg=msg

    @ui.button(label="Send Now",style=discord.ButtonStyle.success)
    async def send_now(self,interaction,button):
        ch=bot.get_channel(PUBLIC_CHANNEL_ID)
        await ch.send(self.msg.content)
        await interaction.response.send_message("✅ Sent",ephemeral=True)
        await log("Manual Send Used")

    @ui.button(label="Schedule",style=discord.ButtonStyle.primary)
    async def schedule(self,interaction,button):
        await interaction.response.send_modal(
            ScheduleModal(self.msg)
        )

    @ui.button(label="Cancel",style=discord.ButtonStyle.danger)
    async def cancel(self,interaction,button):
        await interaction.message.delete()
        await log("Forward Cancelled")

# ================= MESSAGE LISTENER =================

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id!=PRIVATE_CHANNEL_ID:
        return

    embed=discord.Embed(
        title="Forward Control Panel",
        description=message.content,
        color=discord.Color.green()
    )

    await message.channel.send(embed=embed,view=ForwardView(message))

# ================= QUEUE LIST COMMAND =================

@bot.tree.command(name="queue")
async def queue(interaction:discord.Interaction):
    async with aiosqlite.connect("database.db") as db:
        async with db.execute("SELECT id,content,send_time FROM scheduled") as cur:
            rows=await cur.fetchall()

    if not rows:
        return await interaction.response.send_message("Queue Empty")

    text=""
    for sid,content,time in rows:
        text+=f"ID:{sid} | {time}\n"

    await interaction.response.send_message(text)

# ================= EDIT SCHEDULE =================

@bot.tree.command(name="edit_schedule")
@app_commands.describe(id="Schedule ID",new_text="New Message")
async def edit_schedule(interaction,id:int,new_text:str):
    async with aiosqlite.connect("database.db") as db:
        await db.execute(
            "UPDATE scheduled SET content=? WHERE id=?",
            (new_text,id)
        )
        await db.commit()

    await interaction.response.send_message("✅ Schedule Updated")
    await log(f"Schedule Edited ID:{id}")

# ================= DELETE SCHEDULE =================

@bot.tree.command(name="delete_schedule")
async def delete_schedule(interaction,id:int):
    async with aiosqlite.connect("database.db") as db:
        await db.execute(
            "DELETE FROM scheduled WHERE id=?",(id,))
        await db.commit()

    await interaction.response.send_message("🗑 Deleted")
    await log(f"Schedule Deleted ID:{id}")

# ================= READY =================

@bot.event
async def on_ready():
    await setup_db()
    await bot.tree.sync()
    bot.loop.create_task(scheduler())
    print("🔥 Enterprise Forward Bot Ready")

bot.run(TOKEN)
