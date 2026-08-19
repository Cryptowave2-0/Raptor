"""
Cog: /github register and /github remove commands.

All heavy logic lives in Utils/ (Data, DiscordWebhook, GitHubWebhook) —
this file only orchestrates user interaction.
"""

import secrets

import discord
from discord import app_commands
from discord.ext import commands

from Utils.Data import GitHubData, GitHubLink, ServerData
from Utils.DiscordWebhook import DiscordWebhookManager
from Utils.GitHubConfig import DM_TIMEOUT, WEBHOOK_PUBLIC_BASE_URL
from Utils.GitHubWebhook import GitHubAPI, GitHubWebhookServer
from Utils.Log import LogManager, LogTypes
from Utils.Checks import staff_only

OWNER_ID = 1018242749050388610

class GitHubCog(commands.Cog):
    github = app_commands.Group(name="github", description="GitHub notifications in a dedicated channel")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = GitHubData()
        self.serverData = ServerData()
        self.discord_webhook = DiscordWebhookManager(bot)
        self.server = GitHubWebhookServer(self.data, self.discord_webhook)

    @staticmethod
    async def _update_status(channel, message: discord.Message, content: str) -> discord.Message:
        """Edits the status message; if it was deleted in the meantime (the
        README fetch can now take several minutes with retries), we return a
        new message instead of crashing with an uncaught 404 Unknown Message."""
        try:
            await message.edit(content=content)
            return message
        except discord.NotFound:
            return await channel.send(content)

    async def cog_load(self):
        await self.server.start()
        LogManager.log("GitHub webhook server started", LogTypes.EVENT)

    async def cog_unload(self):
        await self.server.stop()
        self.data.close()


    @github.command(name="register", description="Link a GitHub repo to a private notification channel")
    async def register(self, interaction: discord.Interaction):
        channel = await self._get_target_channel(interaction)

        repo_info = await self._prompt_repo(interaction, channel)
        if repo_info is None:
            return
        owner, repo, repo_full_name = repo_info

        if await self._reject_if_already_linked(channel, repo_full_name, interaction.user.id, interaction.guild.id):
            return

        readme = await self._fetch_readme(channel, owner, repo)
        if readme is None:
            return

        avatar_url = await GitHubAPI.fetch_avatar_with_retry(owner)

        embed = await self._build_embed(channel, readme, repo_full_name, avatar_url, interaction.guild.id)
        if embed is None:
            return

        thread_msg = await self._create_post(channel, repo, repo_full_name, embed, avatar_url, interaction.guild.id)
        if thread_msg is None:
            return

        await self._save_link_and_confirm(
            channel, interaction, thread_msg, owner, repo, repo_full_name
        )

    async def _get_target_channel(self, interaction: discord.Interaction):
        """Redirects to a DM if the command is launched in a server; otherwise stays in the current channel."""
        if interaction.guild is not None:
            channel = await interaction.user.create_dm()
            await interaction.response.send_message(
                embed=discord.Embed(description=f"Check {channel.jump_url}"),
                ephemeral=True,
            )
        else:
            channel = interaction.channel
            await interaction.response.send_message(
                embed=discord.Embed(description="We continue here in DM."),
                ephemeral=True,
            )
        return channel

    async def _prompt_repo(self, interaction: discord.Interaction, channel):
        """Asks the user for the repo. Returns (owner, repo, repo_full_name) or None if cancelled/invalid/expired."""

        def check(m: discord.Message) -> bool:
            return m.author.id == interaction.user.id and m.channel.id == channel.id

        await channel.send(
            embed=discord.Embed(
                description=(
                    "Which repo do you want to link? Send me the format `owner/repo`\n"
                    "(e.g., `torvalds/linux`). Type `cancel` to stop."
                )
            )
        )

        try:
            msg = await self.bot.wait_for("message", check=check, timeout=DM_TIMEOUT)
        except TimeoutError:
            await channel.send(
                embed=discord.Embed(description="Time's up, run `/github register` again whenever you want.")
            )
            return None

        content = msg.content.strip()

        if content.lower() == "cancel":
            await channel.send(embed=discord.Embed(description="Operation cancelled."))
            return None

        if "/" not in content:
            await channel.send(
                embed=discord.Embed(description="Invalid format (`owner/repo` expected). Run the command again.")
            )
            return None

        owner, repo = content.split("/", 1)
        return owner, repo, f"{owner}/{repo}"

    async def _reject_if_already_linked(self, channel, repo_full_name: str, user_id: int, server_id: int) -> bool:
        """Checks if the repo is already linked. Returns True (and notifies the user) if it is."""
        existing_link = self.data.find_by_repo_any_author(repo_full_name, server_id)
        if existing_link is None:
            return False

        existing_thread = self.bot.get_channel(existing_link.thread_id)
        mention = existing_thread.mention if existing_thread else "an existing thread"

        if existing_link.author_id == user_id:
            description = f"You already have a post for `{repo_full_name}` : {mention}"
        else:
            description = f"`{repo_full_name}` is already linked by someone else : {mention}"

        await channel.send(embed=discord.Embed(description=description))
        return True

    async def _fetch_readme(self, channel, owner: str, repo: str):
        """Fetches the README. Sends an error message and returns None if it fails."""
        repo_full_name = f"{owner}/{repo}"

        try:
            readme = await GitHubAPI.fetch_readme(owner, repo)
        except Exception as e:
            LogManager.log(f"[GITHUB] fetch_readme ERROR: {type(e).__name__}: {e}", LogTypes.INTERNAL_ERROR)
            await channel.send(
                embed=discord.Embed(title="❌ GitHub API Error", description=f"`{type(e).__name__}: {e}`")
            )
            return None

        if readme is None:
            await channel.send(
                embed=discord.Embed(
                    description=f"Repo `{repo_full_name}` not found or no README.md at the root. Check the name and try again."
                )
            )
            return None

        return readme

    async def _build_embed(self, channel, readme: dict, repo_full_name: str, avatar_url: str, server_id: int):
        LogManager.log("[GITHUB] Building README embed...", LogTypes.EVENT)
        try:
            embed = self.discord_webhook.build_readme_embed(
                readme["text"], readme["base_raw_url"], repo_full_name, avatar_url
            )
            LogManager.log("[GITHUB] README embed created.", LogTypes.EVENT)
            return embed
        except Exception as e:
            LogManager.log(f"[GITHUB] build_readme_embed ERROR: {type(e).__name__}: {e}", LogTypes.INTERNAL_ERROR)
            await channel.send(
                embed=discord.Embed(title="❌ Embed Error", description=f"`{type(e).__name__}: {e}`")
            )
            return None

    async def _create_post(self, channel, repo: str, repo_full_name: str, embed, avatar_url: str, server_id: int):
        LogManager.log("[GITHUB] Creating Discord post...", LogTypes.EVENT)
        try:
            thread_msg = await self.discord_webhook.create_post(
                thread_title=repo,
                embed=embed,
                username=repo_full_name,
                avatar_url=avatar_url,
                server_id=server_id
            )
            LogManager.log(f"[GITHUB] Discord post created: {thread_msg.id}", LogTypes.EVENT)
            return thread_msg
        except Exception as e:
            LogManager.log(f"[GITHUB] create_post ERROR: {type(e).__name__}: {e}", LogTypes.INTERNAL_ERROR)
            await channel.send(
                embed=discord.Embed(title="❌ Discord Webhook Error", description=f"`{type(e).__name__}: {e}`")
            )
            return None

    async def _save_link_and_confirm(
        self, channel, interaction: discord.Interaction, thread_msg, owner: str, repo: str, repo_full_name: str
    ):
        thread = thread_msg.channel
        token = secrets.token_urlsafe(24)
        webhook_secret = secrets.token_hex(32)

        self.data.add(
            GitHubLink(
                token=token,
                server_id=interaction.guild.id,
                secret=webhook_secret,
                thread_id=thread.id,
                author_id=interaction.user.id,
                repo=repo_full_name,
                owner=owner,
                starter_message_id=thread_msg.id,
            )
        )

        webhook_url = f"{WEBHOOK_PUBLIC_BASE_URL}/github/{token}"
        await channel.send(
            embed=discord.Embed(
                description=(
                    f"Post created : {thread.mention}\n\n"
                    f"**GitHub Configuration** (repo {repo_full_name} → Settings → Webhooks → Add webhook) :\n"
                    f"- Payload URL : `{webhook_url}`\n"
                    f"- Content type : `application/json`\n"
                    f"- Secret : `{webhook_secret}`\n"
                    f"- Events : `push` and `releases` at minimum\n\n"
                    f"⚠️ This secret is shown here only once — keep this message. "
                    f"You can remove this link at any time with `/github remove`."
                )
            )
        )

    
    # ── /github remove ──────────────────────────────────────────────────
    @github.command(name="remove", description="Definitively remove a GitHub repo link and its notification thread")
    @app_commands.describe(repo="owner/repo to remove")
    async def remove(self, interaction: discord.Interaction, repo: str):
        link = self.data.find_by_repo(interaction.user.id, repo, interaction.guild.id if interaction.guild else None)
        if link is None:
            await interaction.response.send_message(embed=discord.Embed(description="No repo found under your name for that name."), ephemeral=True)
            return

        is_staff = isinstance(interaction.user, discord.Member) and any(
            r.id in self.serverData.get().staff_role_id for r in interaction.user.roles
        )
        if link.author_id != interaction.user.id and not is_staff:
            await interaction.response.send_message(embed=discord.Embed(description="You don't have permission to remove this repo."), ephemeral=True)
            return

        await self.discord_webhook.delete_thread(link.thread_id)
        self.data.remove(link.token)

        await interaction.response.send_message(
            embed=discord.Embed(description=f"`{link.repo}` removed. Remember to delete the webhook on the GitHub side "
                                            f"(Settings → Webhooks) if you don't plan to link it elsewhere."),
            ephemeral=True,
        )

    @remove.autocomplete("repo")
    async def remove_autocomplete(self, interaction: discord.Interaction, current: str):
        links = self.data.list_by_author(interaction.user.id, current, interaction.guild.id if interaction.guild else None)
        return [app_commands.Choice(name=link.repo, value=link.repo) for link in links[:25]]



    @commands.command(name="github_refresh", aliases=["ghrefresh", "githubrefresh"])
    @staff_only()
    async def github_refresh(self, ctx: commands.Context, repo: str):
        """
        Force to refresh GitHub README
        of a registered repositorie.

        Example :
            sudo github_refresh owner/repo
            sudo ghrefresh owner/repo
        """

        repo = repo.strip()

        if "/" not in repo:
            await ctx.send("❌ Wrong format. Use `owner/repo`.")
            return

        owner, repo_name = repo.split("/", 1)
        repo_full_name = f"{owner}/{repo_name}"
        message = await ctx.send(f"🔄 Refreshing README for `{repo_full_name}`...")
        link = self.data.find_by_repo_any_author(repo_full_name, ctx.guild.id)


        if link is None:
            await self._update_status(ctx.channel, message,f"❌ `{repo_full_name}` is not registered.")
            return


        try:
            readme = await GitHubAPI.fetch_readme_with_retry(owner, repo_name)

        except Exception as e:
            LogManager.log(f"[GITHUB REFRESH] fetch_readme ERROR: {type(e).__name__}: {e}", LogTypes.INTERNAL_ERROR)
            await self._update_status(ctx.channel, message, f"❌ GitHub README fetch failed.\n `{type(e).__name__}: {e}`")
            return

        if readme is None:
            await self._update_status(ctx.channel, message, f"❌ README not found for `{repo_full_name}`.")
            return

        avatar_url = await GitHubAPI.fetch_avatar_with_retry(owner)

        try:
            embed = self.discord_webhook.build_readme_embed(readme["text"], readme["base_raw_url"], repo_full_name, avatar_url)

        except Exception as e:
            LogManager.log(f"[GITHUB REFRESH] build_readme_embed ERROR: {type(e).__name__}: {e}",LogTypes.INTERNAL_ERROR)
            await self._update_status(ctx.channel, message,f"❌ Failed to build README embed.\n`{type(e).__name__}: {e}`")
            return

        try:
            await self.discord_webhook.edit_starter_message(thread_id=link.thread_id, message_id=link.starter_message_id, embed=embed)

        except Exception as e:
            LogManager.log(f"[GITHUB REFRESH] edit_starter_message ERROR: {type(e).__name__}: {e}",LogTypes.INTERNAL_ERROR)
            await self._update_status(ctx.channel, message, f"❌ Failed to update Discord message.\n`{type(e).__name__}: {e}`")
            return

        await self._update_status(
            ctx.channel, message, f"✅ README refreshed successfully for `{repo_full_name}`.")

async def setup(bot: commands.Bot):
    await bot.add_cog(GitHubCog(bot))