import sqlite3
from contextlib import contextmanager
from datetime import datetime

DB_PATH = "tracker.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tracked_games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS view_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                views INTEGER,
                scraped_at TEXT NOT NULL,
                FOREIGN KEY (game_id) REFERENCES tracked_games(id) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_game ON view_snapshots(game_id, scraped_at)")


def add_tracked_game(title, source, url):
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO tracked_games (title, source, url, created_at) VALUES (?, ?, ?, ?)",
            (title, source, url, now),
        )
        if cur.lastrowid:
            return cur.lastrowid
        row = conn.execute("SELECT id FROM tracked_games WHERE url = ?", (url,)).fetchone()
        return row["id"]


def record_snapshot(game_id, views):
    numeric_views = views if isinstance(views, int) else None
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO view_snapshots (game_id, views, scraped_at) VALUES (?, ?, ?)",
            (game_id, numeric_views, datetime.utcnow().isoformat()),
        )


def delete_tracked_game(game_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM tracked_games WHERE id = ?", (game_id,))


def list_tracked_with_latest():
    """Returns each tracked game plus its most recent and previous snapshot,
    so the dashboard can show a trend arrow without extra queries."""
    with get_conn() as conn:
        games = conn.execute("SELECT * FROM tracked_games ORDER BY created_at DESC").fetchall()
        results = []
        for g in games:
            snaps = conn.execute(
                "SELECT views, scraped_at FROM view_snapshots WHERE game_id = ? ORDER BY scraped_at DESC LIMIT 2",
                (g["id"],),
            ).fetchall()
            latest = snaps[0] if len(snaps) > 0 else None
            previous = snaps[1] if len(snaps) > 1 else None
            results.append({
                "id": g["id"],
                "title": g["title"],
                "source": g["source"],
                "url": g["url"],
                "latest_views": latest["views"] if latest else None,
                "latest_scraped_at": latest["scraped_at"] if latest else None,
                "previous_views": previous["views"] if previous else None,
            })
        return results


def get_game(game_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tracked_games WHERE id = ?", (game_id,)).fetchone()
        return dict(row) if row else None


def get_all_games():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM tracked_games").fetchall()]


def get_history(game_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT views, scraped_at FROM view_snapshots WHERE game_id = ? ORDER BY scraped_at ASC",
            (game_id,),
        ).fetchall()
        return [{"views": r["views"], "scraped_at": r["scraped_at"]} for r in rows]
