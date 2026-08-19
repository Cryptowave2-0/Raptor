"""Utilities for loading and reloading Discord bot cogs from the Cogs package."""

from discord.ext import commands
from discord.ext.commands import errors
from pathlib import Path
from Utils.Log import LogTypes
from typing import Optional

COGS_DIR = Path("Cogs")

class CogManager:
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _cog_files(self, cog_name: Optional[str] = None):
        """Generates the names of .py files to process, filtered by cog_name if provided."""
        for path in COGS_DIR.glob("*.py"):
            if path.stem.startswith("_"):
                continue 
            if cog_name is None or cog_name.lower() in path.stem.lower() :
                yield path.stem

    async def load_cogs(self):
        """Loads all cogs in the COGS_DIR, yielding log messages for each."""
        for stem in self._cog_files():
            try:
                await self.bot.load_extension(f"Cogs.{stem}")
                yield (f"Loaded cog: {stem}", LogTypes.EVENT)
            except Exception as e:
                yield (f"Failed to load cog {stem}: {e}", LogTypes.INTERNAL_ERROR)

    async def reload_cogs(self, cog_name: Optional[str] = None):
        """Reloads cogs filtered by cog_name if provided, yielding log messages for each."""
        for stem in self._cog_files(cog_name):
            try:
                await self.bot.reload_extension(f"Cogs.{stem}")
                yield (f"Reloaded cog: {stem}", LogTypes.EVENT)
            except errors.ExtensionNotLoaded:
                await self.bot.load_extension(f"Cogs.{stem}")
                yield (f"Loaded cog: {stem}", LogTypes.EVENT)
            except Exception as e:
                yield (f"Failed to reload cog {stem}: {e}", LogTypes.INTERNAL_ERROR)