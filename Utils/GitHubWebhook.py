"""
GitHub side: read-only API calls (README, avatar) and an aiohttp server that
receives GitHub events (push, release), verifies their HMAC signature, and
propagates changes to Discord via a DiscordWebhookManager.
"""

import base64
import hashlib
import hmac
from typing import Optional
import asyncio
import json

import aiohttp
import discord
from aiohttp import web

from Utils.Data import GitHubData, GitHubLink
from Utils.DiscordWebhook import DiscordWebhookManager
from Utils.GitHubConfig import GITHUB_API_TOKEN, WEBHOOK_PORT
from Utils.Log import LogManager, LogTypes

README_FETCH_TIMEOUT_SECONDS = 300   # 5 minutes par tentative
README_RETRY_DELAY_SECONDS = 600     # 10 minutes entre deux tentatives
README_MAX_ATTEMPTS = 3

AVATAR_FETCH_TIMEOUT_SECONDS = 30
AVATAR_RETRY_DELAY_SECONDS = 10
AVATAR_MAX_ATTEMPTS = 5

class GitHubAPI:
    """Calls the GitHub API to fetch README and avatar."""

    _session: Optional[aiohttp.ClientSession] = None

    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        if cls._session is None or cls._session.closed:
            cls._session = aiohttp.ClientSession()
        return cls._session

    @staticmethod
    def _headers() -> dict:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "Discord-GitHub-Bot",
        }

        if GITHUB_API_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_API_TOKEN}"

        return headers

    @staticmethod
    async def fetch_readme(owner: str, repo: str) -> Optional[dict]:
        """Returns README text and raw base URL."""

        url = f"https://api.github.com/repos/{owner}/{repo}/readme"
        timeout = aiohttp.ClientTimeout(
            total=README_FETCH_TIMEOUT_SECONDS,
            connect=5,
        )

        try:
            session = await GitHubAPI.get_session()

            async with session.get(
                url,
                headers=GitHubAPI._headers(),
                timeout=timeout,  # override par requête, pas par session
            ) as resp:

                if resp.status != 200:
                    LogManager.log(
                        f"[GITHUB] README HTTP {resp.status}: {owner}/{repo}",
                        LogTypes.WARNING
                    )
                    return None

                data = await resp.json()

            text = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            base_raw_url = data["download_url"].rsplit("/", 1)[0] + "/"

            return {"text": text, "base_raw_url": base_raw_url}

        except asyncio.TimeoutError:
            LogManager.log(
                f"[GITHUB] README timeout: {owner}/{repo}",
                LogTypes.INTERNAL_ERROR
            )
            return None

        except aiohttp.ClientError as e:
            LogManager.log(
                f"[GITHUB] README HTTP error: {type(e).__name__}: {e}",
                LogTypes.INTERNAL_ERROR
            )
            return None

        except Exception as e:
            LogManager.log(
                f"[GITHUB] README error: {type(e).__name__}: {e}",
                LogTypes.INTERNAL_ERROR
            )
            return None

    @staticmethod
    async def fetch_readme_with_retry(
        owner: str,
        repo: str,
        max_attempts: int = README_MAX_ATTEMPTS,
        retry_delay: int = README_RETRY_DELAY_SECONDS,
    ) -> Optional[dict]:
        """
        Fetches the README with multiple attempts (same policy as
        fetch_avatar_with_retry).

        - First attempt is immediate
        - Waits retry_delay seconds between attempts
        - Returns the README as soon as an attempt succeeds
        - Returns None if all attempts fail
        """

        for attempt in range(1, max_attempts + 1):

            LogManager.log(
                f"[GITHUB] README fetch attempt "
                f"{attempt}/{max_attempts}: {owner}/{repo}",
                LogTypes.EVENT
            )
 
            readme = await GitHubAPI.fetch_readme(owner, repo)

            if readme is not None:
                LogManager.log(
                    f"[GITHUB] README successfully fetched: "
                    f"{owner}/{repo}",
                    LogTypes.EVENT
                )
                return readme

            if attempt < max_attempts:
                LogManager.log(
                    f"[GITHUB] README fetch failed for {owner}/{repo}. "
                    f"Retrying in {retry_delay} seconds "
                    f"(attempt {attempt + 1}/{max_attempts})...",
                    LogTypes.WARNING
                )
                await asyncio.sleep(retry_delay)

        LogManager.log(
            f"[GITHUB] README fetch permanently failed: {owner}/{repo}",
            LogTypes.INTERNAL_ERROR
        )
        return None

    @staticmethod
    async def fetch_avatar(owner: str) -> Optional[str]:
        url = f"https://api.github.com/users/{owner}"

        session = await GitHubAPI.get_session()
        timeout = aiohttp.ClientTimeout(
            total=AVATAR_FETCH_TIMEOUT_SECONDS,
            connect=5,
        )

        try:

            async with session.get(url, headers=GitHubAPI._headers(), timeout=timeout) as resp:

                if resp.status != 200:

                    LogManager.log(f"[GITHUB] Avatar HTTP {resp.status}: {owner}", LogTypes.WARNING)

                    return None

                data = await resp.json()

                return data.get("avatar_url")

        except asyncio.TimeoutError:
            LogManager.log(
                f"[GITHUB] Avatar timeout: {owner}",
                LogTypes.WARNING
            )
            return None

        except aiohttp.ClientError as e:
            LogManager.log(
                f"[GITHUB] Avatar HTTP error: "
                f"{type(e).__name__}: {e}",
                LogTypes.WARNING
            )
            return None

        except Exception as e:
            LogManager.log(
                f"[GITHUB] Avatar error: "
                f"{type(e).__name__}: {e}",
                LogTypes.INTERNAL_ERROR
            )
            return None

    @staticmethod
    async def fetch_avatar_with_retry(
        owner: str,
        max_attempts: int = AVATAR_MAX_ATTEMPTS,
        retry_delay: int = AVATAR_RETRY_DELAY_SECONDS,
    ) -> Optional[str]:
        """
        Fetch the GitHub avatar with multiple attempts.

        - First attempt is immediate
        - Waits retry_delay seconds between attempts
        - Returns the URL as soon as an attempt succeeds
        - Returns None if all attempts fail
        """

        for attempt in range(1, max_attempts + 1):

            LogManager.log(
                f"[GITHUB] Avatar fetch attempt "
                f"{attempt}/{max_attempts}: {owner}",
                LogTypes.EVENT
            )

            avatar_url = await GitHubAPI.fetch_avatar(owner)

            if avatar_url:
                LogManager.log(
                    f"[GITHUB] Avatar successfully fetched: "
                    f"{owner}",
                    LogTypes.EVENT
                )

                return avatar_url

            if attempt < max_attempts:

                LogManager.log(
                    f"[GITHUB] Avatar fetch failed for {owner}. "
                    f"Retrying in {retry_delay} seconds "
                    f"(attempt {attempt + 1}/{max_attempts})...",
                    LogTypes.EVENT
                )

                await asyncio.sleep(retry_delay)

        LogManager.log(
            f"[GITHUB] Avatar fetch permanently failed: {owner}",
            LogTypes.INTERNAL_ERROR
        )

        return None      


class GitHubWebhookServer:
    """Server aiohttp : receives GitHub events, verifies HMAC signature, and relays to Discord via DiscordWebhookManager."""

    def __init__(self, data: GitHubData, discord_webhook: DiscordWebhookManager):
        self.data = data
        self.discord_webhook = discord_webhook
        self.app = web.Application()
        self.app.router.add_post("/github/{token}", self._handle_webhook)
        self.runner: Optional[web.AppRunner] = None

    async def start(self) -> None:
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        await web.TCPSite(self.runner, "0.0.0.0", WEBHOOK_PORT).start()

    async def stop(self) -> None:
        if self.runner:
            await self.runner.cleanup()

    @staticmethod
    def _verify_signature(body: bytes, signature_header: str, secret: str) -> bool:
        if not signature_header or not signature_header.startswith("sha256="):
            return False
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature_header[len("sha256="):])

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        token = request.match_info["token"]
        link = self.data.get(token)
        if link is None:
            return web.Response(status=404, text="Unknown token")

        try:
            body = await request.read()

        except ConnectionResetError:
            LogManager.log(
                f"[GITHUB WEBHOOK] Client disconnected before request body was fully received "
                f"(source: {request.remote}).",
                LogTypes.EVENT
            )
            return web.Response(status=400, text="Connection closed")

        except asyncio.CancelledError:
            raise

        except Exception as e:
            LogManager.log(
                f"[GITHUB WEBHOOK] Failed to read request body: "
                f"{type(e).__name__}: {e}",
                LogTypes.INTERNAL_ERROR
            )
            return web.Response(status=400, text="Invalid request")
    
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not self._verify_signature(body, signature, link.secret):
            return web.Response(status=401, text="Invalid signature")

        event = request.headers.get("X-GitHub-Event", "")
        signature = request.headers.get("X-Hub-Signature-256", "")

        if not self._verify_signature(
            body,
            signature,
            link.secret
        ):
            return web.Response(
                status=401,
                text="Invalid signature"
            )

        try:
            payload = json.loads(
                body.decode("utf-8")
            )
        except (UnicodeDecodeError, json.JSONDecodeError):
            return web.Response(
                status=400,
                text="Invalid JSON"
            )

        if event == "push":
            await self._handle_push(payload, link)
        elif event == "release" and payload.get("action") == "published":
            await self._handle_release(payload, link)

        return web.Response(status=200, text="OK")

    async def _handle_push(self, payload: dict, link: GitHubLink) -> None:
        commits = payload.get("commits", [])
        if not commits:
            return

        desc = "\n".join(
            f"[`{c['id'][:7]}`]({c['url']}) {c['message'].splitlines()[0]} — {c['author']['name']}"
            for c in commits[:5]
        )
        embed = discord.Embed(
            title=f"📦 {len(commits)} commit(s)",
            description=desc,
            color=discord.Color.blurple(),
            url=payload.get("compare"),
        )
        
        try:
            avatar_url = await GitHubAPI.fetch_avatar(link.owner)
        except Exception:
            avatar_url = None

        await self.discord_webhook.send_to_thread(
            thread_id=link.thread_id,
            embed=embed,
            username=link.repo,
            avatar_url=avatar_url,
        )

        readme_touched = any(
            "readme.md" in (f.lower() for f in c.get("added", []) + c.get("modified", []))
            for c in commits
        )
        if readme_touched:
            asyncio.create_task(self._update_readme_with_retry(link, avatar_url))

    async def _update_readme_with_retry(self, link: GitHubLink, avatar_url: Optional[str]) -> None:
        """Refetch le README (avec retry) et édite le message de départ du
        thread. Tourne en arrière-plan, sans bloquer la réponse HTTP au
        webhook GitHub — avec README_MAX_ATTEMPTS tentatives possibles,
        espacées de README_RETRY_DELAY_SECONDS, ça peut prendre plusieurs
        dizaines de minutes dans le pire cas."""
        owner, repo = link.repo.split("/", 1)
        readme = await GitHubAPI.fetch_readme_with_retry(owner, repo)
        if readme is None:
            return  # déjà loggé dans fetch_readme_with_retry

        new_embed = self.discord_webhook.build_readme_embed(
            readme["text"], readme["base_raw_url"], link.repo, avatar_url
        )
        await self.discord_webhook.edit_starter_message(
            thread_id=link.thread_id, message_id=link.starter_message_id, embed=new_embed
        )

    async def _handle_release(self, payload: dict, link: GitHubLink) -> None:
        release = payload["release"]
        embed = discord.Embed(
            title=f"🚀 New release : {release['name'] or release['tag_name']}",
            description=(release.get("body") or "")[:500],
            url=release["html_url"],
            color=discord.Color.green(),
        )
        
        try:
            avatar_url = await GitHubAPI.fetch_avatar(link.owner)
        except Exception as e:
            LogManager.log(
                f"[GITHUB] Avatar unavailable: {type(e).__name__}: {e}",
                LogTypes.EVENT
            )
            avatar_url = None
        
        await self.discord_webhook.send_to_thread(
            thread_id=link.thread_id, embed=embed, username=link.repo, avatar_url=avatar_url
        )