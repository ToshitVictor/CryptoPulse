
import sqlite3
import hashlib
import secrets
import hmac
from datetime import timedelta
from pathlib import Path
from datetime import datetime, timezone


# Database location
ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = ROOT / "data" / "cryptopulse.db"


def get_connection():
    """Create a connection to the SQLite database."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    return connection


def hash_password(password):
    """Securely hash a password using PBKDF2."""
    salt = secrets.token_bytes(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        600_000
    )

    return salt.hex() + "$" + password_hash.hex()


def verify_password(password, stored_hash):
    """Verify a password against its stored hash."""
    try:
        salt_hex, hash_hex = stored_hash.split("$")

        salt = bytes.fromhex(salt_hex)

        password_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            600_000
        )

        return hmac.compare_digest(
            password_hash.hex(),
            hash_hex
        )

    except (ValueError, TypeError):
        return False



def initialize_database():
    """Create the required database tables."""

    with get_connection() as connection:

        # USERS TABLE
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TEXT NOT NULL
            )
        """)

        # Add email column to existing databases
        columns = [
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(users)"
            ).fetchall()
        ]

        if "email" not in columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN email TEXT"
            )

        # Prevent duplicate email addresses
        connection.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email
            ON users(email)
            WHERE email IS NOT NULL AND email != ''
        """)

        # ACTIVITY LOGS TABLE
        connection.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # PASSWORD RESET OTP TABLE
        connection.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_otps (
                email TEXT PRIMARY KEY,
                otp_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)


def register_user(username, email, password):
    username = username.strip()
    email = email.strip().lower()

    if len(username) < 3:
        return False, "Username must contain at least 3 characters."

    if len(username) > 30:
        return False, "Username must not exceed 30 characters."

    if "@" not in email or "." not in email.split("@")[-1]:
        return False, "Please enter a valid email address."

    if len(password) < 8:
        return False, "Password must contain at least 8 characters."

    password_hash = hash_password(password)

    try:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO users
                (username, email, password_hash, role, created_at)
                VALUES (?, ?, ?, 'user', ?)
                """,
                (
                    username,
                    email,
                    password_hash,
                    datetime.now(timezone.utc).isoformat()
                )
            )

        return True, "Account created successfully."

    except sqlite3.IntegrityError:
        return False, "Username or email is already registered."
def get_user_by_username(username):
    """Find a user by username."""

    with get_connection() as connection:

        user = connection.execute(
            "SELECT * FROM users WHERE username = ?",
            (username.strip(),)
        ).fetchone()

    return dict(user) if user else None


def log_activity(user_id, action, details=""):
    """Record a user's activity."""

    with get_connection() as connection:

        connection.execute(
            """
            INSERT INTO activity_logs
            (user_id, action, details, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                user_id,
                action,
                details,
                datetime.now(timezone.utc).isoformat()
            )
        )


def get_all_users():
    """Retrieve registered users without password hashes."""

    with get_connection() as connection:

        users = connection.execute("""
            SELECT id, username, role, created_at
            FROM users
            ORDER BY created_at DESC
        """).fetchall()

    return [dict(user) for user in users]


def get_recent_activities(limit=100):
    """Retrieve recent user activities."""

    with get_connection() as connection:

        activities = connection.execute("""
            SELECT
                activity_logs.id,
                users.username,
                activity_logs.action,
                activity_logs.details,
                activity_logs.created_at
            FROM activity_logs
            JOIN users ON users.id = activity_logs.user_id
            ORDER BY activity_logs.id DESC
            LIMIT ?
        """, (limit,)).fetchall()

    return [dict(activity) for activity in activities]

def get_user_by_email(email):
    with get_connection() as connection:
        user = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email.strip().lower(),)
        ).fetchone()

    return dict(user) if user else None

def create_password_reset_otp(email, otp):
    """Store a securely hashed OTP with a 5-minute expiry."""

    email = email.strip().lower()
    salt = secrets.token_bytes(16)

    otp_hash = hashlib.pbkdf2_hmac(
        "sha256",
        otp.encode("utf-8"),
        salt,
        100_000
    )

    now = datetime.now(timezone.utc)

    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO password_reset_otps
            (email, otp_hash, salt, expires_at, attempts, created_at)
            VALUES (?, ?, ?, ?, 0, ?)
            """,
            (
                email,
                otp_hash.hex(),
                salt.hex(),
                (now + timedelta(minutes=5)).isoformat(),
                now.isoformat()
            )
        )


def verify_password_reset_otp(email, otp):
    """Verify OTP, expiry, and failed attempt limit."""

    email = email.strip().lower()

    with get_connection() as connection:
        record = connection.execute(
            """
            SELECT * FROM password_reset_otps
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        if not record:
            return False, "No OTP request found. Request a new OTP."

        if datetime.now(timezone.utc) >= datetime.fromisoformat(
            record["expires_at"]
        ):
            connection.execute(
                "DELETE FROM password_reset_otps WHERE email = ?",
                (email,)
            )
            return False, "OTP expired. Please request a new one."

        if record["attempts"] >= 5:
            connection.execute(
                "DELETE FROM password_reset_otps WHERE email = ?",
                (email,)
            )
            return False, "Too many attempts. Request a new OTP."

        salt = bytes.fromhex(record["salt"])

        entered_hash = hashlib.pbkdf2_hmac(
            "sha256",
            otp.encode("utf-8"),
            salt,
            100_000
        )

        if not hmac.compare_digest(
            entered_hash.hex(),
            record["otp_hash"]
        ):
            connection.execute(
                """
                UPDATE password_reset_otps
                SET attempts = attempts + 1
                WHERE email = ?
                """,
                (email,)
            )
            return False, "Incorrect OTP. Please try again."

        return True, "OTP verified successfully."


def delete_password_reset_otp(email):
    """Delete OTP after successful password reset."""

    with get_connection() as connection:
        connection.execute(
            "DELETE FROM password_reset_otps WHERE email = ?",
            (email.strip().lower(),)
        )


def reset_user_password(email, new_password):
    """Update password after OTP verification."""

    email = email.strip().lower()

    if len(new_password) < 8:
        return False, "Password must contain at least 8 characters."

    password_hash = hash_password(new_password)

    with get_connection() as connection:
        result = connection.execute(
            """
            UPDATE users
            SET password_hash = ?
            WHERE email = ?
            """,
            (password_hash, email)
        )

        if result.rowcount == 0:
            return False, "Account not found."

        connection.execute(
            "DELETE FROM password_reset_otps WHERE email = ?",
            (email,)
        )

    return True, "Password reset successfully."


