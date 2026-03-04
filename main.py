import discord
from discord import app_commands
import aiohttp
import asyncio
import aiosqlite
import os

TOKEN = os.getenv("TOKEN")
API_URL = "https://api.warframestat.us/pc"

intents = discord.Intents.default()
intents.message_content = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# ---------- DATABASE ----------

async def init_db():
    async with aiosqlite.connect("database.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sent_alerts (
                id TEXT PRIMARY KEY
            )
        """)
        await db.commit()

async def alert_exists(alert_id):
    async with aiosqlite.connect("database.db") as db:
        async with db.execute("SELECT 1 FROM sent_alerts WHERE id = ?", (alert_id,)) as cursor:
            return await cursor.fetchone() is not None

async def save_alert(alert_id):
    async with aiosqlite.connect("database.db") as db:
        await db.execute("INSERT OR IGNORE INTO sent_alerts (id) VALUES (?)", (alert_id,))
        await db.commit()

# ---------- WARFRAME CHECK ----------

async def check_warframe():
    await bot.wait_until_ready()
    await init_db()

    while not bot.is_closed():
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(API_URL) as response:
                    data = await response.json()

            alerts = data.get("alerts", [])

            for alert in alerts:
                alert_id = alert["id"]

                if not await alert_exists(alert_id):
                    mission = alert["mission"]["type"]
                    node = alert["mission"]["node"]
                    reward = alert["mission"]["reward"].get("asString", "Unknown")
                    expiry = alert["expiry"]

                    for guild in bot.guilds:
                        channel = discord.utils.get(guild.text_channels, name="warframe-alerts")
                        if channel:
                            embed = discord.Embed(
                                title="🚨 Нова Alert місія!",
                                color=0xff0000
                            )
                            embed.add_field(name="Тип", value=mission, inline=True)
                            embed.add_field(name="Локація", value=node, inline=True)
                            embed.add_field(name="Нагорода", value=reward, inline=False)
                            embed.add_field(name="Закінчується", value=expiry, inline=False)
                            await channel.send(embed=embed)

                    await save_alert(alert_id)

        except Exception as e:
            print("Error:", e)

        await asyncio.sleep(180)

# ---------- SLASH COMMAND ----------

@tree.command(name="alerts", description="Показати активні Alerts")
async def alerts(interaction: discord.Interaction):
    async with aiohttp.ClientSession() as session:
        async with session.get(API_URL) as response:
            data = await response.json()

    alerts = data.get("alerts", [])

    if not alerts:
        await interaction.response.send_message("Немає активних Alerts.")
        return

    message = ""
    for alert in alerts[:5]:
        mission = alert["mission"]["type"]
        node = alert["mission"]["node"]
        reward = alert["mission"]["reward"].get("asString", "Unknown")
        message += f"**{mission}** | {node} | {reward}\n"

    await interaction.response.send_message(message)

# ---------- EVENTS ----------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await tree.sync()
    bot.loop.create_task(check_warframe())

bot.run(TOKEN)
