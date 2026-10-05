import aiosqlite
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from config import DB_PATH

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE,
                unique_code TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                admin_notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_submissions_email ON submissions(email COLLATE NOCASE);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_submissions_user_id ON submissions(user_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions(status);")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS appeals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                appeal_text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                admin_response TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (submission_id) REFERENCES submissions(id)
            );
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS support_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                message_text TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        # Backward-compatible columns for PASS and Key
        for col in ["pass_code", "key_code"]:
            try:
                await db.execute(f"ALTER TABLE submissions ADD COLUMN {col} TEXT;")
            except Exception:
                pass

        await db.commit()

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

async def is_email_registered(email: str, exclude_submission_id: Optional[int] = None) -> bool:
    """Checks if email is already present in submissions database (case-insensitive)."""
    clean_email = email.strip().lower()
    async with aiosqlite.connect(DB_PATH) as db:
        if exclude_submission_id:
            cursor = await db.execute(
                "SELECT id FROM submissions WHERE LOWER(email) = ? AND id != ? LIMIT 1",
                (clean_email, exclude_submission_id)
            )
        else:
            cursor = await db.execute(
                "SELECT id FROM submissions WHERE LOWER(email) = ? LIMIT 1",
                (clean_email,)
            )
        row = await cursor.fetchone()
        return row is not None

async def get_submission_by_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Gets the latest submission for a given Telegram user ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM submissions WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

async def get_all_submissions_by_user(user_id: int) -> List[Dict[str, Any]]:
    """Gets all submissions made by a given Telegram user ID ordered newest to oldest."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM submissions WHERE user_id = ? ORDER BY id DESC",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def get_submission_by_id(submission_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM submissions WHERE id = ?",
            (submission_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

async def create_submission(user_id: int, username: Optional[str], email: str, pass_code: str, key_code: str) -> int:
    ts = now_iso()
    clean_email = email.strip().lower()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO submissions (user_id, username, full_name, email, unique_code, pass_code, key_code, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
            """,
            (user_id, username, pass_code.strip(), clean_email, key_code.strip(), pass_code.strip(), key_code.strip(), ts, ts)
        )
        await db.commit()
        return cursor.lastrowid

async def update_submission_resubmit(submission_id: int, email: str, pass_code: str, key_code: str) -> None:
    ts = now_iso()
    clean_email = email.strip().lower()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE submissions
            SET email = ?, full_name = ?, unique_code = ?, pass_code = ?, key_code = ?, status = 'PENDING', admin_notes = NULL, updated_at = ?
            WHERE id = ?
            """,
            (clean_email, pass_code.strip(), key_code.strip(), pass_code.strip(), key_code.strip(), ts, submission_id)
        )
        await db.commit()

async def update_submission_status(submission_id: int, new_status: str, admin_notes: Optional[str] = None) -> Optional[Dict[str, Any]]:
    ts = now_iso()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if admin_notes is not None:
            await db.execute(
                "UPDATE submissions SET status = ?, admin_notes = ?, updated_at = ? WHERE id = ?",
                (new_status, admin_notes, ts, submission_id)
            )
        else:
            await db.execute(
                "UPDATE submissions SET status = ?, updated_at = ? WHERE id = ?",
                (new_status, ts, submission_id)
            )
        await db.commit()

        cursor = await db.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def get_queue_info(submission_id: int) -> Dict[str, int]:
    """
    Computes queue position for a PENDING submission:
    - position: 1-based index among pending submissions ordered by id
    - ahead_count: how many pending submissions are before this one
    - total_pending: total number of pending submissions
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor_pos = await db.execute(
            "SELECT COUNT(*) FROM submissions WHERE status = 'PENDING' AND id <= ?",
            (submission_id,)
        )
        pos_row = await cursor_pos.fetchone()
        position = pos_row[0] if pos_row else 1

        cursor_total = await db.execute(
            "SELECT COUNT(*) FROM submissions WHERE status = 'PENDING'"
        )
        tot_row = await cursor_total.fetchone()
        total_pending = tot_row[0] if tot_row else 1

        ahead_count = max(0, position - 1)
        return {
            "position": position,
            "ahead_count": ahead_count,
            "total_pending": total_pending
        }

async def get_admin_stats() -> Dict[str, int]:
    async with aiosqlite.connect(DB_PATH) as db:
        stats = {
            "total": 0,
            "pending": 0,
            "in_review": 0,
            "accepted": 0,
            "disapproved": 0,
            "can_resubmit": 0,
            "appeals_pending": 0
        }
        cursor = await db.execute("SELECT status, COUNT(*) FROM submissions GROUP BY status")
        rows = await cursor.fetchall()
        for status, count in rows:
            stats["total"] += count
            if status == "PENDING":
                stats["pending"] = count
            elif status == "IN_REVIEW":
                stats["in_review"] = count
            elif status == "ACCEPTED":
                stats["accepted"] = count
            elif status == "DISAPPROVED":
                stats["disapproved"] = count
            elif status == "CAN_RESUBMIT":
                stats["can_resubmit"] = count

        cursor_app = await db.execute("SELECT COUNT(*) FROM appeals WHERE status = 'PENDING'")
        app_row = await cursor_app.fetchone()
        stats["appeals_pending"] = app_row[0] if app_row else 0

        return stats

async def get_submissions_by_status(status: str, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM submissions WHERE status = ? ORDER BY id ASC LIMIT ? OFFSET ?",
            (status, limit, offset)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def search_submissions(query: str) -> List[Dict[str, Any]]:
    clean = f"%{query.strip().lower()}%"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM submissions 
            WHERE LOWER(email) LIKE ? OR LOWER(unique_code) LIKE ? OR LOWER(full_name) LIKE ?
            ORDER BY id DESC LIMIT 10
            """,
            (clean, clean, clean)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def create_appeal(submission_id: int, user_id: int, appeal_text: str) -> int:
    ts = now_iso()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO appeals (submission_id, user_id, appeal_text, status, created_at, updated_at)
            VALUES (?, ?, ?, 'PENDING', ?, ?)
            """,
            (submission_id, user_id, appeal_text.strip(), ts, ts)
        )
        await db.commit()
        return cursor.lastrowid

async def get_appeal_by_id(appeal_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM appeals WHERE id = ?", (appeal_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def get_pending_appeals(limit: int = 10) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM appeals WHERE status = 'PENDING' ORDER BY id ASC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def update_appeal_status(appeal_id: int, status: str, admin_response: Optional[str] = None) -> Optional[Dict[str, Any]]:
    ts = now_iso()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "UPDATE appeals SET status = ?, admin_response = ?, updated_at = ? WHERE id = ?",
            (status, admin_response, ts, appeal_id)
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM appeals WHERE id = ?", (appeal_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def save_support_message(user_id: int, username: Optional[str], message_text: str) -> int:
    ts = now_iso()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO support_messages (user_id, username, message_text, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, username, message_text.strip(), ts)
        )
        await db.commit()
        return cursor.lastrowid

async def get_all_submissions() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM submissions ORDER BY id ASC")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def register_user(user_id: int, username: Optional[str], first_name: Optional[str]) -> None:
    """Saves or updates a user in the bot_users table whenever they interact."""
    ts = now_iso()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO bot_users (user_id, username, first_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                updated_at = excluded.updated_at
            """,
            (user_id, username, first_name, ts, ts)
        )
        await db.commit()

async def get_all_user_ids() -> List[int]:
    """Returns a list of all unique Telegram user IDs who have interacted with the bot or submitted."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Combine bot_users and submissions to ensure all users are reached
        cursor = await db.execute(
            """
            SELECT DISTINCT user_id FROM (
                SELECT user_id FROM bot_users
                UNION
                SELECT user_id FROM submissions
            )
            """
        )
        rows = await cursor.fetchall()
        return [r[0] for r in rows]

async def get_total_users_count() -> int:
    ids = await get_all_user_ids()
    return len(ids)

