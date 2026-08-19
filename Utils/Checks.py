import discord
from discord import app_commands


from Utils.Env import _get

from Utils.Data import ServerData
data = ServerData()

def staff_only():
    async def predicate(interaction: discord.Interaction) -> bool:

        if interaction.guild is None:
            return False

        server_data = data.get(interaction.guild.id)

        if server_data is None:
            return False

        if not server_data.staff_role_id:
            return False

        if not isinstance(interaction.user, discord.Member):
            return False

        return any(
            role.id == server_data.staff_role_id
            for role in interaction.user.roles
        )

    return app_commands.check(predicate)

def admin_only():
    async def predicate(interaction: discord.Interaction) -> bool:

        if interaction.guild is None:
            return False

        if not interaction.user.guild_permissions.administrator:
            return False

        if not isinstance(interaction.user, discord.Member):
            return False

        return True

    return app_commands.check(predicate)

def server_owner_only():
    async def predicate(interaction: discord.Interaction) -> bool:

        if interaction.guild is None:
            return False

        if interaction.guild.owner_id != interaction.user.id:
            return False

        if not isinstance(interaction.user, discord.Member):
            return False

        return True

    return app_commands.check(predicate)

def bot_owner_only():
    async def predicate(interaction: discord.Interaction) -> bool:

        print(interaction.client.owner_id)

        if interaction.guild is None:
            return False

        if interaction.user.id != int(_get("BOT_OWNER")):
            return False

        if not isinstance(interaction.user, discord.Member):
            return False

        return True

    return app_commands.check(predicate)