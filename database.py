import os
import shutil
import aiosqlite
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from config import DB_PATH

async def init_db():
    local_db = os.path.abspath(os.path.join(os.path.dirname(__file__), "bot_database.sqlite"))
    if DB_PATH != local_db and os.path.exists(local_db) and not os.path.exists(DB_PATH):
        try:
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            shutil.copy2(local_db, DB_PATH)
        except Exception:
            pass

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA busy_timeout = 5000;")
        await db.execute("PRAGMA synchronous = NORMAL;")
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

        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)

        # Backward-compatible columns for PASS, Key, Resubmissions, and Approval Tier
        for col in ["pass_code", "key_code", "resubmitted_at", "resubmit_unlocked_at", "tier"]:
            try:
                await db.execute(f"ALTER TABLE submissions ADD COLUMN {col} TEXT;")
            except Exception:
                pass

        try:
            await db.execute("ALTER TABLE submissions ADD COLUMN is_resubmission INTEGER DEFAULT 0;")
        except Exception:
            pass

        await db.commit()

async def get_setting(key: str, default: str = "") -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row[0] if row else default

async def set_setting(key: str, value: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)", (key, value.strip()))
        await db.commit()

async def get_channel_url() -> str:
    from config import REQUIRED_CHANNEL
    val = await get_setting("channel_url")
    return val if val else REQUIRED_CHANNEL

async def get_video_url() -> str:
    from config import TUTORIAL_VIDEO_URL
    val = await get_setting("video_url")
    return val if val else TUTORIAL_VIDEO_URL

async def get_support_handle() -> str:
    from config import SUPPORT_HANDLE
    val = await get_setting("support_handle")
    return val if val else SUPPORT_HANDLE

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

async def get_submission_by_email(email: str) -> Optional[Dict[str, Any]]:
    clean_email = email.strip().lower()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM submissions WHERE LOWER(email) = ? ORDER BY id DESC LIMIT 1",
            (clean_email,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

def check_8_hour_cooldown(timestamp_str: str) -> tuple[bool, int, int]:
    """
    Checks if 8 hours have passed since timestamp_str.
    Returns: (can_resubmit: bool, remaining_hours: int, remaining_mins: int)
    """
    try:
        past_dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
    except Exception:
        return (True, 0, 0)
    now_dt = datetime.now(timezone.utc)
    elapsed_secs = (now_dt - past_dt).total_seconds()
    cooldown_secs = 8 * 3600  # 8 hours = 28,800 seconds
    if elapsed_secs >= cooldown_secs:
        return (True, 0, 0)
    diff = cooldown_secs - elapsed_secs
    hours = int(diff // 3600)
    mins = int((diff % 3600) // 60)
    return (False, hours, mins)

def check_resubmit_eligibility(submission: Dict[str, Any]) -> tuple[bool, str, int, int]:
    """
    Checks if a submission is eligible for resubmission.
    Rules:
    1. Must have status == 'CAN_RESUBMIT' (admin explicitly clicked 'Can Resubmit' or unlocked via appeal).
    2. Must have elapsed >= 8 hours since admin unlocked (resubmit_unlocked_at).
    
    Returns: (can_resubmit: bool, reason: str, remaining_hours: int, remaining_mins: int)
    """
    status = submission.get("status")
    if status == "ACCEPTED":
        return (False, "ACCEPTED", 0, 0)

    if status != "CAN_RESUBMIT":
        return (False, "NOT_UNLOCKED", 0, 0)

    unlocked_at = submission.get("resubmit_unlocked_at") or submission.get("updated_at")
    if not unlocked_at:
        return (False, "NOT_UNLOCKED", 0, 0)

    can_resub, rem_h, rem_m = check_8_hour_cooldown(unlocked_at)
    if not can_resub:
        return (False, "COOLDOWN_ACTIVE", rem_h, rem_m)

    return (True, "ELIGIBLE", 0, 0)

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
        try:
            cursor = await db.execute(
                """
                INSERT INTO submissions (user_id, username, full_name, email, unique_code, pass_code, key_code, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
                """,
                (user_id, username, pass_code.strip(), clean_email, key_code.strip(), pass_code.strip(), key_code.strip(), ts, ts)
            )
            await db.commit()
            return cursor.lastrowid
        except Exception:
            # If an existing record exists for this email, update it with the new credentials
            cursor = await db.execute("SELECT id FROM submissions WHERE LOWER(email) = ?", (clean_email,))
            row = await cursor.fetchone()
            if row:
                sub_id = row[0]
                await db.execute(
                    """
                    UPDATE submissions 
                    SET user_id = ?, username = ?, full_name = ?, unique_code = ?, pass_code = ?, key_code = ?, 
                        status = 'PENDING', admin_notes = NULL, updated_at = ?
                    WHERE id = ?
                    """,
                    (user_id, username, pass_code.strip(), key_code.strip(), pass_code.strip(), key_code.strip(), ts, sub_id)
                )
                await db.commit()
                return sub_id
            raise

async def update_submission_resubmit(submission_id: int, email: str, pass_code: str, key_code: str) -> None:
    ts = now_iso()
    clean_email = email.strip().lower()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE submissions
            SET email = ?, full_name = ?, unique_code = ?, pass_code = ?, key_code = ?, 
                status = 'PENDING', is_resubmission = 1, resubmitted_at = ?, admin_notes = NULL, updated_at = ?
            WHERE id = ?
            """,
            (clean_email, pass_code.strip(), key_code.strip(), pass_code.strip(), key_code.strip(), ts, ts, submission_id)
        )
        await db.commit()

async def get_resubmitted_submissions(limit: int = 5, offset: int = 0) -> List[Dict[str, Any]]:
    """Gets all submissions that were resubmitted by users."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM submissions WHERE is_resubmission = 1 ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def get_resubmitted_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM submissions WHERE is_resubmission = 1")
        row = await cursor.fetchone()
        return row[0] if row else 0

async def update_submission_status(
    submission_id: int, 
    new_status: str, 
    admin_notes: Optional[str] = None,
    tier: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    ts = now_iso()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if new_status == "CAN_RESUBMIT":
            # Setting CAN_RESUBMIT starts the 8-hour unlock countdown for the user
            await db.execute(
                "UPDATE submissions SET status = ?, admin_notes = ?, resubmit_unlocked_at = ?, updated_at = ? WHERE id = ?",
                (new_status, admin_notes, ts, ts, submission_id)
            )
        elif new_status == "PENDING":
            # Undo action resets to PENDING
            await db.execute(
                "UPDATE submissions SET status = 'PENDING', admin_notes = ?, updated_at = ? WHERE id = ?",
                (admin_notes, ts, submission_id)
            )
        elif new_status == "ACCEPTED":
            tier_val = (tier or "NORMAL").upper()
            if admin_notes is not None:
                await db.execute(
                    "UPDATE submissions SET status = 'ACCEPTED', tier = ?, admin_notes = ?, updated_at = ? WHERE id = ?",
                    (tier_val, admin_notes, ts, submission_id)
                )
            else:
                await db.execute(
                    "UPDATE submissions SET status = 'ACCEPTED', tier = ?, updated_at = ? WHERE id = ?",
                    (tier_val, ts, submission_id)
                )
        else:
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
    """Investor/Inventory style statistics breakdown."""
    async with aiosqlite.connect(DB_PATH) as db:
        stats = {
            "total": 0,
            "new_total": 0,
            "new_pending": 0,
            "resubmitted_total": 0,
            "resubmitted_pending": 0,
            "pending": 0,
            "in_review": 0,
            "accepted": 0,
            "disapproved": 0,
            "can_resubmit": 0,
            "appeals_pending": 0,
            "resubmitted": 0
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

        # New accounts inventory (is_resubmission = 0 or NULL)
        cursor_new = await db.execute("SELECT COUNT(*) FROM submissions WHERE is_resubmission = 0 OR is_resubmission IS NULL")
        row_new = await cursor_new.fetchone()
        stats["new_total"] = row_new[0] if row_new else 0

        cursor_new_pend = await db.execute("SELECT COUNT(*) FROM submissions WHERE (is_resubmission = 0 OR is_resubmission IS NULL) AND status = 'PENDING'")
        row_new_pend = await cursor_new_pend.fetchone()
        stats["new_pending"] = row_new_pend[0] if row_new_pend else 0

        # Resubmitted accounts inventory
        cursor_resub = await db.execute("SELECT COUNT(*) FROM submissions WHERE is_resubmission = 1")
        resub_row = await cursor_resub.fetchone()
        stats["resubmitted_total"] = resub_row[0] if resub_row else 0
        stats["resubmitted"] = stats["resubmitted_total"]

        cursor_resub_pend = await db.execute("SELECT COUNT(*) FROM submissions WHERE is_resubmission = 1 AND status = 'PENDING'")
        resub_pend_row = await cursor_resub_pend.fetchone()
        stats["resubmitted_pending"] = resub_pend_row[0] if resub_pend_row else 0

        # Appeals pending
        cursor_app = await db.execute("SELECT COUNT(*) FROM appeals WHERE status = 'PENDING'")
        app_row = await cursor_app.fetchone()
        stats["appeals_pending"] = app_row[0] if app_row else 0

        # Normal vs Premium accepted accounts
        cursor_norm = await db.execute("SELECT COUNT(*) FROM submissions WHERE status = 'ACCEPTED' AND (tier = 'NORMAL' OR tier IS NULL OR tier = '')")
        row_norm = await cursor_norm.fetchone()
        stats["accepted_normal"] = row_norm[0] if row_norm else 0

        cursor_prem = await db.execute("SELECT COUNT(*) FROM submissions WHERE status = 'ACCEPTED' AND tier = 'PREMIUM'")
        row_prem = await cursor_prem.fetchone()
        stats["accepted_premium"] = row_prem[0] if row_prem else 0

        return stats

async def get_submissions_by_tier(tier: str, status: str = "ACCEPTED", limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        tier_upper = (tier or "NORMAL").upper()
        if tier_upper == "NORMAL":
            cursor = await db.execute(
                "SELECT * FROM submissions WHERE status = ? AND (tier = 'NORMAL' OR tier IS NULL OR tier = '') ORDER BY id ASC LIMIT ? OFFSET ?",
                (status, limit, offset)
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM submissions WHERE status = ? AND tier = ? ORDER BY id ASC LIMIT ? OFFSET ?",
                (status, tier_upper, limit, offset)
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def get_submissions_count_by_tier(tier: str, status: str = "ACCEPTED") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        tier_upper = (tier or "NORMAL").upper()
        if tier_upper == "NORMAL":
            cursor = await db.execute(
                "SELECT COUNT(*) FROM submissions WHERE status = ? AND (tier = 'NORMAL' OR tier IS NULL OR tier = '')",
                (status,)
            )
        else:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM submissions WHERE status = ? AND tier = ?",
                (status, tier_upper)
            )
        row = await cursor.fetchone()
        return row[0] if row else 0

async def get_submissions_by_status(status: str, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM submissions WHERE status = ? ORDER BY id ASC LIMIT ? OFFSET ?",
            (status, limit, offset)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def get_submissions_count_by_status(status: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM submissions WHERE status = ?", (status,))
        row = await cursor.fetchone()
        return row[0] if row else 0

async def get_submissions_batch(limit: int = 5, status: Optional[str] = "PENDING") -> List[Dict[str, Any]]:
    """Gets up to 'limit' submissions from pool (prioritizing 'status' if specified, filling from general pool if needed)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        results = []
        if status:
            cursor = await db.execute(
                "SELECT * FROM submissions WHERE status = ? ORDER BY id ASC LIMIT ?",
                (status, limit)
            )
            rows = await cursor.fetchall()
            results.extend([dict(r) for r in rows])

        # If we need more to reach limit, fill from other submissions
        if len(results) < limit:
            remaining = limit - len(results)
            exclude_ids = [r["id"] for r in results]
            if exclude_ids:
                placeholders = ",".join(["?"] * len(exclude_ids))
                cursor = await db.execute(
                    f"SELECT * FROM submissions WHERE id NOT IN ({placeholders}) ORDER BY id ASC LIMIT ?",
                    (*exclude_ids, remaining)
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM submissions ORDER BY id ASC LIMIT ?",
                    (remaining,)
                )
            rows = await cursor.fetchall()
            results.extend([dict(r) for r in rows])

        return results

async def get_user_eligible_resubmissions(user_id: int) -> List[Dict[str, Any]]:
    """Gets submissions for this user that were unlocked by admin (status == 'CAN_RESUBMIT')."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM submissions WHERE user_id = ? AND status = 'CAN_RESUBMIT' ORDER BY id DESC",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def get_user_disapproved_submissions(user_id: int) -> List[Dict[str, Any]]:
    """Gets submissions for this user that are DISAPPROVED (eligible for appeal)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM submissions WHERE user_id = ? AND status = 'DISAPPROVED' ORDER BY id DESC",
            (user_id,)
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
            WHERE LOWER(email) LIKE ? 
               OR LOWER(unique_code) LIKE ? 
               OR LOWER(full_name) LIKE ?
               OR LOWER(COALESCE(pass_code, '')) LIKE ?
               OR LOWER(COALESCE(key_code, '')) LIKE ?
            ORDER BY id DESC LIMIT 10
            """,
            (clean, clean, clean, clean, clean)
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

