import discord, random
from discord import app_commands
from discord.ext import commands

class EventCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        channel = discord.utils.get(member.guild.channels, name=f'landing-and-launch-pad'.lower())
        embed = discord.Embed(title='New member !', description=f'{member.mention} has just landed !', color=discord.Color.green())
        embed.set_thumbnail(url=member.display_avatar.url)
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        channel = discord.utils.get(member.guild.channels, name='landing-and-launch-pad'.lower())
        embed = discord.Embed(title='Member left ...', description=f'{member.mention} took off !', color=discord.Color.red())
        embed.set_thumbnail(url=member.display_avatar.url)
        await channel.send(embed=embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EventCog(bot))