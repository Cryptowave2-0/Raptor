"""
SQLite storage for links between GitHub repositories and Discord threads.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List, Literal, Optional

DB_PATH = Path("Data/Database.db")
DB_PATH.parent.mkdir(exist_ok=True)


@dataclass
class ServerLink:
    server_id: int
    forum_id: int
    staff_role_id: int
    update_channel_id: int
    welcome_channel_id: int
    goodbye_channel_id: int

ServerLinkField = Literal[
            "forum_id",
            "staff_role_id",
            "update_channel_id",
            "welcome_channel_id",
            "goodbye_channel_id",
        ]


@dataclass
class GitHubLink:
    token: str
    server_id: int
    secret: str           # per-link HMAC secret (GitHub signature)
    thread_id: int
    author_id: int
    repo: str            # "owner/repo"
    owner: str
    starter_message_id: int



class ServerData:
    """Access CRUD to the server_links table."""

    def __init__(self, db_path: Path = DB_PATH):
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

        

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS server_links (
                server_id INTEGER PRIMARY KEY,
                forum_id INTEGER NOT NULL,
                staff_role_id INTEGER NOT NULL,
                update_channel_id INTEGER NOT NULL,
                welcome_channel_id INTEGER NOT NULL,
                goodbye_channel_id INTEGER NOT NULL
            )
            """
        )
        self._conn.commit()

    def add(self, link: ServerLink) -> None:
        """Add a new ServerLink to the database."""
        self._conn.execute(
            """
            INSERT INTO server_links (server_id, forum_id, staff_role_id, update_channel_id, welcome_channel_id, goodbye_channel_id)
            VALUES (:server_id, :forum_id, :staff_role_id, :update_channel_id, :welcome_channel_id, :goodbye_channel_id)
            """,
            link.__dict__,
        )
        self._conn.commit()

    def remove(self, id: int) -> None:
        """Remove a ServerLink from the database by its id."""
        self._conn.execute("DELETE FROM server_links WHERE server_id = ?", (id,))
        self._conn.commit()

    def get(self, id: int) -> Optional[ServerLink]:
        """Get a ServerLink by its id."""
        row = self._conn.execute(
            "SELECT * FROM server_links WHERE server_id = ?", (id,)
        ).fetchone()
        return self._row_to_link(row) if row else None

    def update(self, server_id: int, field: ServerLinkField, value: int) -> None:

        if field not in ServerLinkField.__args__:
            raise ValueError(f"Invalid server link field: {field}")
        
        """Update a field of a ServerLink in the database."""
        self._conn.execute(
            f"UPDATE server_links SET {field} = ? WHERE server_id = ?",
            (value, server_id)
        )
        self._conn.commit()

    def list_repo(self, server_id: int, prefix: str = None) -> List[GitHubLink]:
        """List all GitHubLinks for a given server, optionally filtered by repo prefix."""
        if not prefix is None:
            rows = self._conn.execute(
                "SELECT * FROM github_links WHERE server_id = ? AND repo LIKE ? ORDER BY repo",
                (server_id, f"%{prefix}%"),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM github_links WHERE server_id = ? ORDER BY repo",
                (server_id,),
            ).fetchall()
        return [self._row_to_link(r) for r in rows]

    @staticmethod
    def _row_to_link(row: sqlite3.Row) -> GitHubLink:
        return GitHubLink(**dict(row))

    def close(self) -> None:
        self._conn.close()




class GitHubData:
    """Access CRUD to the github_links table."""

    def __init__(self, db_path: Path = DB_PATH):
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

        self.GitHubLinkField = Literal[
            "token",
            "server_id",
            "secret",
            "thread_id",
            "author_id",
            "repo",
            "owner",
            "starter_message_id"
        ]

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS github_links (
                token TEXT PRIMARY KEY,
                server_id INTEGER NOT NULL,
                secret TEXT NOT NULL,
                thread_id INTEGER NOT NULL,
                author_id INTEGER NOT NULL,
                repo TEXT NOT NULL,
                owner TEXT NOT NULL,
                starter_message_id INTEGER NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_author_repo ON github_links(author_id, repo)"
        )

        # self._conn.execute("""
        #     ALTER TABLE github_links
        #     ADD COLUMN server_id INTEGER DEFAULT 1430143613710630924
        # """)

        self._conn.commit()

    def add(self, link: GitHubLink) -> None:
        """Add a new GitHubLink to the database."""
        self._conn.execute(
            """
            INSERT INTO github_links (token, server_id, secret, thread_id, author_id, repo, owner, starter_message_id)
            VALUES (:token, :server_id, :secret, :thread_id, :author_id, :repo, :owner, :starter_message_id)
            """,
            link.__dict__,
        )
        self._conn.commit()

    def remove(self, token: str) -> None:
        """Remove a GitHubLink from the database by its token."""
        self._conn.execute("DELETE FROM github_links WHERE token = ?", (token,))
        self._conn.commit()

    def get(self, token: str) -> Optional[GitHubLink]:
        """Get a GitHubLink by its token."""
        row = self._conn.execute(
            "SELECT * FROM github_links WHERE token = ?", (token,)
        ).fetchone()
        return self._row_to_link(row) if row else None

    def find_by_repo(self, author_id: int, repo: str, server_id: Optional[int] = None) -> Optional[GitHubLink]:
        """Find an existing link for this repo and author.

        If server_id is provided, only search for links in that server.
        """
        if server_id is None:
            row = self._conn.execute(
                "SELECT * FROM github_links WHERE author_id = ? AND LOWER(repo) = LOWER(?)",
                (author_id, repo),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT * FROM github_links WHERE author_id = ? AND LOWER(repo) = LOWER(?) AND server_id = ?",
                (author_id, repo, server_id),
            ).fetchone()
        return self._row_to_link(row) if row else None

    def find_by_repo_any_author(self, repo: str, server_id: int) -> Optional[GitHubLink]:
        """Find an existing link for this repo, whatever the author — used
        to prevent two posts for the same repo."""
        row = self._conn.execute(
            "SELECT * FROM github_links WHERE LOWER(repo) = LOWER(?) AND server_id = ?",
            (repo, server_id),
        ).fetchone()
        return self._row_to_link(row) if row else None

    def list_by_author(self, author_id: int, prefix: str = "", server_id: Optional[int] = None) -> List[GitHubLink]:
        """List all GitHubLinks for a given author, optionally filtered by repo prefix."""
        if server_id is None:
            rows = self._conn.execute(
                "SELECT * FROM github_links WHERE author_id = ? AND repo LIKE ? ORDER BY repo",
                (author_id, f"%{prefix}%"),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM github_links WHERE author_id = ? AND repo LIKE ? AND server_id = ? ORDER BY repo",
                (author_id, f"%{prefix}%", server_id),
            ).fetchall()
        return [self._row_to_link(r) for r in rows]

    @staticmethod
    def _row_to_link(row: sqlite3.Row) -> GitHubLink:
        return GitHubLink(**dict(row))

    def close(self) -> None:
        self._conn.close()


