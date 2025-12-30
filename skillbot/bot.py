import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv


def run():
    load_dotenv()
    TOKEN = os.getenv("DEV_DISCORD_TOKEN")
    if TOKEN is None:
        raise ValueError("No DISCORD_TOKEN")

    bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

    @bot.event
    async def on_ready():
        print(f"Logged in as {bot.user}")

    asyncio.run(bot.start(TOKEN))
