import random
import re

import discord
from discord.ext import commands

from Utils.Checks import bot_owner_only


HELLO_RESPONSE = [
    "Hi there!",
    "Hello!",
    "Hey there!",
    "Greetings!",
    "Howdy!",
    "Hi!",
    "Hey!",
    "Hello there!",
    "Hiya!",
    "Yo!",
]

HELLO_COMMANDS = [
    "hello",
    "hi",
    "hey",
    "greetings",
    "howdy",
    "yo",
]

OWNER_ID = 1018242749050388610


class ExtraCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.hello_regex = re.compile(
            r"\b(?:"
            + "|".join(re.escape(command) for command in HELLO_COMMANDS)
            + r")\b",
            re.IGNORECASE,
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return
        
        if self.hello_regex.search(message.content):
            response = random.choice(HELLO_RESPONSE)
            await message.channel.send(response)


    @commands.command(name="reload", aliases=["rl"],)
    @bot_owner_only()
    async def reload_command(self, ctx: commands.Context, cog_name: str = None):
        """
        Reload an Cog or all Cogs.

        sudo reload
        sudo reload example
        sudo rl example
        """

        if ctx.author.id != OWNER_ID:
            return

        if cog_name is None:
            message = await ctx.send("🔄 Reloading all cogs...")
            results = []

            async for result, log_type in self.bot.cog_manager.reload_cogs():
                results.append(result)

        else:
            message = await ctx.send(f"🔄 Reloading `{cog_name}`...")
            results = []

            async for result, log_type in self.bot.cog_manager.reload_cogs(cog_name):
                results.append(result)

        if not results:
            if cog_name:
                await message.edit( content=(f"❌ No cog found matching "f"`{cog_name}`."))

            else:
                await message.edit(content="❌ No cog to reload.")

            return

        output = "\n".join(results)

        if len(output) > 1800:
            output = output[:1800] + "\n..."

        await message.edit(content=(f"✅ **Reload completed**\n```text\n{output}\n```"))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ExtraCog(bot))