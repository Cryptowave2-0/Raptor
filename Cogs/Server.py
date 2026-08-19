"""
Cogs/Server.py
This cog handles server-related commands and events.
"""

import discord
from discord import app_commands
from discord.ext import commands

from Utils.Log import LogManager, LogTypes
from Utils.Data import ServerData, ServerLink
from Utils.Checks import admin_only

class ServerCog(commands.Cog):
    server = app_commands.Group(name="server", description="Server-related commands")
    set_group = app_commands.Group(name="set",description="Configure server settings")

    server.add_command(set_group)

    def __init__(self, bot):
        self.bot = bot
        self.data = ServerData()

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        # Handle actions when the bot joins a new server
        LogManager.log(f"Joined new server: {guild.name} (ID: {guild.id})", LogTypes.EVENT)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        # Handle actions when the bot is removed from a server
        LogManager.log(f"Removed from server: {guild.name} (ID: {guild.id})", LogTypes.EVENT)

    @server.command(name='info')
    async def server_info(self, interaction: discord.Interaction):
        """Displays information about the server."""
        guild = interaction.guild
        embed = discord.Embed(title=f"{guild.name} Info", color=discord.Color.blue())
        embed.add_field(name="Server ID", value=guild.id, inline=True)
        embed.add_field(name="Member Count", value=guild.member_count, inline=True)
        embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
        embed.add_field(
            name="📅 Created", 
            value=f"<t:{int(guild.created_at.timestamp())}:F>\n<t:{int(guild.created_at.timestamp())}:R>", 
            inline=True)
        embed.add_field(name="Roles Count", value=len(guild.roles), inline=True)
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @set_group.command(name='welcome')
    @admin_only()
    async def server_set_welcome(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set the welcome channel of the server."""
        self.data.update(interaction.guild.id, "welcome_channel_id", channel.id)
        await interaction.response.send_message(
            embed=discord.Embed(
                title='Server Update',
                description=f'The welcome channel has been set to {channel.mention}'
            )
        )

    @set_group.command(name='goodbye')
    @admin_only()
    async def server_set_goodbye(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set the goodbye channel of the server."""
        self.data.update(interaction.guild.id, "goodbye_channel_id", channel.id)
        await interaction.response.send_message(
            embed=discord.Embed(
                title='Server Update',
                description=f'The goodbye channel has been set to {channel.mention}'
            )
        )

    @set_group.command(name='staff')
    @admin_only()
    async def server_set_staff(self, interaction: discord.Interaction, role: discord.Role):
        """Set the staff role of the server."""
        self.data.update(interaction.guild.id, "staff_role_id", role.id)
        await interaction.response.send_message(
            embed=discord.Embed(
                title='Server Update',
                description=f'The staff role for bot permissions has been set to {role.mention}'
            )
        )

    @set_group.command(name='forum')
    @admin_only()
    async def server_set_forum(self, interaction: discord.Interaction, channel: discord.ForumChannel):
        """Set the forum channel of the server."""
        self.data.update(interaction.guild.id, "forum_id", channel.id)
        await interaction.response.send_message(
            embed=discord.Embed(
                title='Server Update',
                description=f'The forum channel has been set to {channel.mention}'
            )
        )
        
    @set_group.command(name='update')
    @admin_only()
    async def server_set_update(self, interaction: discord.Interaction, channel: discord.ForumChannel): 
        """Set the update channel of the server for bots updates."""
        self.data.update(interaction.guild.id, "update_channel_id", channel.id)
        await interaction.response.send_message(
            embed=discord.Embed(
                title='Server Update',
                description=f'The update channel has been set to {channel.mention}'
            )
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerCog(bot))