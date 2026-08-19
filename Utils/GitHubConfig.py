"""
Configuration for the GitHub <-> Discord Forum module.

All sensitive values come from the .env file (loaded by main.py before
importing the cogs). Discord IDs (channels, roles) are hard-coded
constants here and should be adapted for your server.
"""

import os
from Utils.Env import _get


# ── Discord ──
DM_TIMEOUT = 600   # seconds for the user to respond in dm to /github register

# ── GitHub ──
GITHUB_API_TOKEN = _get("GITHUB_API_TOKEN", required=False)   # optional, avoids the rate limit 60/h
# Note: no more global HMAC secret — each link has its own (see Utils/Data.py, GitHubLink.secret)

# ── Serveur webhook (recieve events GitHub) ──
WEBHOOK_PORT = int(_get("WEBHOOK_PORT"))   # server port, must be open
WEBHOOK_PUBLIC_BASE_URL = _get("WEBHOOK_PUBLIC_BASE_URL")   # http, no domain/HTTPS for now