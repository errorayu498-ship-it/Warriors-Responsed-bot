import discord
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup Logging for advanced error handling (Railway logs me show hoga)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Discord Intents setup (Message content read karne ke liye zaroori hai)
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    logging.info(f'✅ Warrior is Ready Brooo!\nLogged in as {client.user}')

@client.event
async def on_message(message):
    # Bot apne ya dusre bots ke messages ko ignore kare (infinite loop se bachne ke liye)
    if message.author.bot:
        return

    # Env variables se Channel IDs lena
    try:
        SOURCE_CHANNEL_ID = int(os.getenv('SOURCE_CHANNEL_ID'))
        TARGET_CHANNEL_ID = int(os.getenv('TARGET_CHANNEL_ID'))
    except TypeError:
        logging.error("❌ Environment variables SOURCE_CHANNEL_ID ya TARGET_CHANNEL_ID set nahi hain ya galat hain.")
        return

    # Check karna ke msg private channel se aya hai
    if message.channel.id == SOURCE_CHANNEL_ID:
        target_channel = client.get_channel(TARGET_CHANNEL_ID)
        
        if target_channel is None:
            logging.error(f"❌ Target channel (ID: {TARGET_CHANNEL_ID}) nahi mila. Bot ko us channel me access nahi hai.")
            return
        
        try:
            # Attachments (Images/Files) handle karna
            files = []
            if message.attachments:
                for attachment in message.attachments:
                    files.append(await attachment.to_file())
            
            # Message same-to-same post karna (text + files + embeds)
            await target_channel.send(
                content=message.content,
                files=files,
                embeds=message.embeds
            )
            logging.info(f"📤 Message successfully forwarded from {message.author.name}")
            
        except discord.errors.Forbidden:
            logging.error("❌ Permission Error: Bot ke paas public channel me message send karne ki permission nahi hai.")
        except discord.errors.HTTPException as e:
            logging.error(f"❌ HTTP Error (Message shayad bohot lamba hai ya file badi hai): {e}")
        except Exception as e:
            logging.error(f"❌ An unexpected error occurred: {e}")

# Bot run karna
if __name__ == '__main__':
    TOKEN = os.getenv('BOT_TOKEN')
    if not TOKEN:
        logging.error("❌ BOT_TOKEN environment variable is missing!")
    else:
        client.run(TOKEN)
