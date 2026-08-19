"""
Manages the unique and reusable Discord Webhook ("GitHubBridge") for the Forum.

This webhook creates posts, posts commits/releases and edits the
README — never the bot directly — so that each post appears under
the "owner/repo" identity with the GitHub author's avatar.
"""

import re
from typing import Optional
from urllib.parse import quote

import discord
from discord.ext import commands

from Utils.Data import GitHubData, GitHubLink, ServerData, ServerLink

IMAGE_MD_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
IMAGE_HTML_RE = re.compile(r"\\?<img\b([^>]*)/?>", re.IGNORECASE)
SRC_ATTR_RE = re.compile(r'src\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
ALT_ATTR_RE = re.compile(r'alt\s*=\s*["\']([^"\']*)["\']', re.IGNORECASE)

class DiscordWebhookManager:
    WEBHOOK_NAME = "GitHubBridge"

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = ServerData()
        self._webhook: Optional[discord.Webhook] = None

    async def get_webhook(self, server_id: int) -> discord.Webhook:
        """Returns the unique webhook for the Forum, creating it if it doesn't exist yet."""
        if self._webhook is not None:
            return self._webhook
        
        forum_id = self.data.get(server_id).forum_id
        
        forum = self.bot.get_channel(forum_id)
        if forum is None:
            try:
                forum = await self.bot.fetch_channel(forum_id)
            except discord.NotFound:
                raise RuntimeError(
                    f"FORUM_CHANNEL_ID ({forum_id}) not found — "
                    "check the ID and ensure the bot is on that server."
                )

        webhooks = await forum.webhooks()
        existing = discord.utils.get(webhooks, name=self.WEBHOOK_NAME)
        self._webhook = existing or await forum.create_webhook(name=self.WEBHOOK_NAME)
        return self._webhook

    async def create_post(
        self, *, thread_title: str, embed: discord.Embed, username: str, server_id: int, avatar_url: Optional[str]
    ) -> discord.WebhookMessage:
        """Creates a new post in the Forum with the given title, embed, username, and avatar."""
        webhook = await self.get_webhook(server_id)
        return await webhook.send(
            embed=embed,
            username=username,
            avatar_url=avatar_url,
            thread_name=thread_title,
            wait=True,
        )

    async def send_to_thread(
        self, *, thread_id: int, embed: discord.Embed, username: str, avatar_url: Optional[str]
    ) -> discord.WebhookMessage:
        """Posts a message in an existing thread (commit, release...)."""
        webhook = await self.get_webhook()
        return await webhook.send(
            embed=embed,
            username=username,
            avatar_url=avatar_url,
            thread=discord.Object(id=thread_id),
            wait=True,
        )

    async def edit_starter_message(self, *, thread_id: int, message_id: int, embed: discord.Embed) -> None:
        """Edits the starter message of a thread (used for the live README)."""
        webhook = await self.get_webhook()
        await webhook.edit_message(message_id, embed=embed, thread=discord.Object(id=thread_id))

    async def delete_thread(self, thread_id: int) -> None:
        thread = self.bot.get_channel(thread_id)
        if thread:
            await thread.delete()

    @staticmethod
    def build_readme_embed(
        readme_text: str, base_raw_url: str, repo_full_name: str, avatar_url: Optional[str]
    ) -> discord.Embed:
        """Convertit le markdown/HTML GitHub en Embed Discord affichable.
 
        - chemins d'images relatifs -> résolus en URLs absolues raw.githubusercontent.com
          (et encodés : les espaces/caractères spéciaux dans un nom de fichier
          cassent l'URL sinon, ex: "recovery section.png")
        - ![alt](url) markdown ET <img src="..."> HTML -> [🖼️ alt](url) :
          Discord ne rend jamais ces deux syntaxes, même dans un embed, donc
          on en fait des liens cliquables
        - la première image trouvée (peu importe la syntaxe d'origine) devient
          l'image principale de l'embed
        """
        hero_image: Optional[str] = None
 
        def _resolve(path: str) -> str:
            if path.startswith(("http://", "https://")):
                return path
            return base_raw_url + quote(path, safe="/")
 
        def _replace_md(match: re.Match) -> str:
            nonlocal hero_image
            alt, path = match.group(1) or "image", match.group(2)
            url = _resolve(path)
            if hero_image is None:
                hero_image = url
            return f"[🖼️ {alt}]({url})"
 
        def _replace_html(match: re.Match) -> str:
            nonlocal hero_image
            attrs = match.group(1)
            src_match = SRC_ATTR_RE.search(attrs)
            if not src_match:
                return ""  # <img> sans src, rien à faire
            alt_match = ALT_ATTR_RE.search(attrs)
            alt = alt_match.group(1) if alt_match else "image"
            url = _resolve(src_match.group(1))
            if hero_image is None:
                hero_image = url
            return f"[🖼️ {alt}]({url})"
 
        text = IMAGE_HTML_RE.sub(_replace_html, readme_text)
        text = IMAGE_MD_RE.sub(_replace_md, text)
        truncated = text[:3900]
        suffix = "\n\n*(README tronqué, voir le repo pour la suite)*" if len(text) > 3900 else ""
 
        embed = discord.Embed(
            title=repo_full_name,
            description=truncated + suffix,
            color=discord.Color.blurple(),
            url=f"https://github.com/{repo_full_name}",
        )
        if hero_image:
            embed.set_image(url=hero_image)
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        return embed