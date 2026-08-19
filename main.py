import discord, os

from discord.ext import commands
from discord import app_commands

from dotenv import load_dotenv, dotenv_values
load_dotenv()

from Utils.Log import LogManager, LogTypes
from Utils.Cog import CogManager

class Bot(commands.Bot):
    def __init__(self, command_prefix, intents, TOKEN, **options):
        super().__init__(command_prefix=command_prefix, intents=intents, **options)
        self.TOKEN = TOKEN
        self.dir_path = os.path.dirname(os.path.realpath(__file__))
        self.cog_manager = CogManager(self)

    async def setup_hook(self):
        results = [item async for item in self.cog_manager.load_cogs()]
        LogManager.logs(results)

    async def on_ready(self):
        LogManager.log(f"Bot is connected as {self.user.display_name}", LogTypes.EVENT)
        await self.tree.sync()
            

client = Bot(["sudo ", "su ", ">sudo ", "!sudo "], intents=discord.Intents.all(), TOKEN=dotenv_values(".env")["TOKEN"])
client.run(client.TOKEN)