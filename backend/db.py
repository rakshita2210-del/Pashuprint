"""
db.py
-----
This is THE database layer for PashuPrint.

There is exactly ONE SQLite database file (pashuprint.db) and this module
is the only place that talks to it directly. Every other file (routers,
services, main.py) must go through the functions in this file instead of
opening its own connection or defining its own tables.

Design choices (kept intentionally simple for a hackathon MVP):
- Plain sqlite3, no ORM. Rows are returned as plain dicts so the rest of
  the app doesn't need to know anything about SQLite specifics.
- Every function opens a short-lived connection, does its work, and closes
  it. This is simple and safe enough for an MVP; a bigger project would use
  connection pooling instead.
- cow_id (e.g. "COW-1182") is the primary key for an animal, supplied by
  the caller. This matches the identity documents / policy paperwork
  livestock already carry in the field.
"""

import sqlite3
import json
import re
from datetime import datetime, timezone
from typing import Optional

DB_PATH = "pashuprint.db"

# Pattern + minimum digit-width used by generate_cow_id() below.
_COW_ID_PREFIX = "COW-"
_COW_ID_MIN_DIGITS = 4
_COW_ID_PATTERN = re.compile(r"^COW-(\d+)$")


def _now() -> str:
    """Return the current UTC time as an ISO-8601 string, for timestamp columns."""
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> sqlite3.Connection:
    """
    Open a new connection to the SQLite database.

    row_factory = sqlite3.Row lets us access columns by name (row["cow_id"])
    instead of by index, and we convert those into plain dicts before
    returning them from this module so callers never touch sqlite3 objects.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enforce foreign key constraints (off by default in SQLite).
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict]:
    return dict(row) if row is not None else None


def init_db() -> None:
    """
    Create all tables if they don't already exist.

    Safe to call every time the app starts up (CREATE TABLE IF NOT EXISTS
    is a no-op if the table is already there), so main.py just calls this
    once on startup.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS animals (
                cow_id             TEXT PRIMARY KEY,
                breed              TEXT,
                age                INTEGER,
                owner_name         TEXT NOT NULL,
                policy_id          TEXT,
                registration_date  TEXT NOT NULL,
                muzzle_photo_path  TEXT,
                status             TEXT NOT NULL DEFAULT 'active'
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS embeddings (
                cow_id           TEXT NOT NULL,
                embedding_vector TEXT NOT NULL,
                registered_at    TEXT NOT NULL,
                FOREIGN KEY (cow_id) REFERENCES animals (cow_id)
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS verifications (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                cow_id             TEXT NOT NULL,
                verification_type  TEXT NOT NULL,
                photo_path         TEXT,
                top_match_cow_id   TEXT,
                similarity_score   REAL,
                result_status      TEXT NOT NULL,
                timestamp          TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS fraud_flags (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                cow_id      TEXT NOT NULL,
                flag_type   TEXT NOT NULL,
                details     TEXT,
                created_at  TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS agents (
                agent_id       TEXT PRIMARY KEY,
                name           TEXT NOT NULL,
                password_hash  TEXT NOT NULL,
                role           TEXT NOT NULL
            )
            """
        )

        conn.commit()
    finally:
        conn.close()


# ---------- animals ----------

def generate_cow_id() -> str:
    """
    Work out the next PashuPrint Cow ID, e.g. "COW-0004" after
    COW-0001/0002/0003 already exist.

    How it works (kept deliberately simple for a hackathon/SQLite MVP --
    no UUIDs, no separate counter table, no external ID service):
    1. Read every existing cow_id out of the animals table.
    2. Pick out the ones that match the "COW-<digits>" shape and find the
       highest number among them. Anything that doesn't match (a
       malformed or legacy id) is just skipped, not treated as an error.
    3. Return highest + 1, formatted as COW-<padded number>.
       Padding is at least 4 digits (COW-0001) but grows automatically
       once the number itself needs more digits (COW-0999 -> COW-1000 ->
       ... -> COW-10000), so it never truncates a larger number.
    4. If there are no valid existing ids at all, this returns COW-0001.

    This function only *reads* the animals table -- it does not insert
    anything and does not reserve the id. Nothing is written to the
    database until register_animal() actually inserts the row, so if a
    registration is rejected before that insert (e.g. by a duplicate-photo
    check), no id is "used up" -- the very next call to generate_cow_id()
    will simply propose the same number again.

    Known limitation (acceptable for an MVP): if two registrations run at
    the exact same instant, they could both compute the same next number.
    SQLite's primary key on animals.cow_id will reject the second INSERT
    with an IntegrityError in that case -- see routers/registration.py for
    how that's handled. A production system would use a database-level
    sequence or a transaction with locking instead.
    """
    conn = get_connection()
    try:
        rows = conn.execute("SELECT cow_id FROM animals").fetchall()
    finally:
        conn.close()

    highest = 0
    for row in rows:
        match = _COW_ID_PATTERN.match(row["cow_id"] or "")
        if not match:
            continue  # malformed/legacy id -- skip it, don't crash
        highest = max(highest, int(match.group(1)))

    next_number = highest + 1
    width = max(_COW_ID_MIN_DIGITS, len(str(next_number)))
    return f"{_COW_ID_PREFIX}{str(next_number).zfill(width)}"


def register_animal(
    owner_name: str,
    breed: Optional[str] = None,
    age: Optional[int] = None,
    policy_id: Optional[str] = None,
    muzzle_photo_path: Optional[str] = None,
    cow_id: Optional[str] = None,
) -> dict:
    """
    Insert a new row into animals. status defaults to 'active'.

    cow_id is now OPTIONAL: if omitted, one is generated automatically via
    generate_cow_id(). This is the normal path used by the FastAPI
    /register endpoint, since vets/surveyors no longer type in a Cow ID
    themselves. cow_id can still be passed in explicitly by other callers
    (scripts, tests, an admin/import tool) if needed -- that still works
    exactly as before.

    Raises sqlite3.IntegrityError if cow_id already exists (it's the
    primary key) -- routers/registration.py catches this and turns it
    into a clean HTTP error.
    """
    if cow_id is None:
        cow_id = generate_cow_id()

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO animals
                (cow_id, breed, age, owner_name, policy_id,
                 registration_date, muzzle_photo_path, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
            """,
            (cow_id, breed, age, owner_name, policy_id, _now(), muzzle_photo_path),
        )
        conn.commit()
    finally:
        conn.close()
    return get_animal(cow_id)


def get_animal(cow_id: str) -> Optional[dict]:
    """Fetch a single animal by cow_id. Returns None if not found."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM animals WHERE cow_id = ?", (cow_id,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_all_animals() -> list[dict]:
    """Fetch every registered animal. Used for building the mock candidate list at verify-time."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM animals").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_animal_status(cow_id: str, status: str) -> Optional[dict]:
    """Update an animal's status (e.g. 'active' -> 'claimed'). Returns the updated row, or None if not found."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE animals SET status = ? WHERE cow_id = ?", (status, cow_id)
        )
        conn.commit()
    finally:
        conn.close()
    return get_animal(cow_id)


# ---------- embeddings ----------

def add_embedding(cow_id: str, embedding_vector: list) -> None:
    """
    Store an embedding vector for a cow_id.

    embedding_vector is stored as a JSON string (SQLite has no native array
    type). When the real ResNet50 model is plugged in, it will produce the
    same shape of Python list, so this function does not need to change.
    """
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO embeddings (cow_id, embedding_vector, registered_at) VALUES (?, ?, ?)",
            (cow_id, json.dumps(embedding_vector), _now()),
        )
        conn.commit()
    finally:
        conn.close()


def get_embedding(cow_id: str) -> Optional[list]:
    """Fetch the most recently stored embedding for a cow_id, decoded back into a list."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT embedding_vector FROM embeddings WHERE cow_id = ? ORDER BY registered_at DESC LIMIT 1",
            (cow_id,),
        ).fetchone()
        return json.loads(row["embedding_vector"]) if row else None
    finally:
        conn.close()


# ---------- verifications ----------

def log_verification(
    cow_id: str,
    verification_type: str,
    result_status: str,
    photo_path: Optional[str] = None,
    top_match_cow_id: Optional[str] = None,
    similarity_score: Optional[float] = None,
) -> dict:
    """
    Insert a row into verifications.

    verification_type is a free-form label describing when the check
    happened, e.g. "register", "claim", or "verify".
    """
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO verifications
                (cow_id, verification_type, photo_path, top_match_cow_id,
                 similarity_score, result_status, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (cow_id, verification_type, photo_path, top_match_cow_id,
             similarity_score, result_status, _now()),
        )
        conn.commit()
        new_id = cur.lastrowid
    finally:
        conn.close()

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM verifications WHERE id = ?", (new_id,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_verifications_for_animal(cow_id: str) -> list[dict]:
    """Fetch verification history for one animal, newest first."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM verifications WHERE cow_id = ? ORDER BY timestamp DESC",
            (cow_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
def get_verification_history(cow_id: str) -> list[dict]:
    """Alias for get_verifications_for_animal() for frontend/API compatibility."""
    return get_verifications_for_animal(cow_id)


# ---------- fraud_flags ----------

def add_fraud_flag(cow_id: str, flag_type: str, details: Optional[str] = None) -> dict:
    """Insert a new fraud flag row."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO fraud_flags (cow_id, flag_type, details, created_at) VALUES (?, ?, ?, ?)",
            (cow_id, flag_type, details, _now()),
        )
        conn.commit()
        new_id = cur.lastrowid
    finally:
        conn.close()

    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM fraud_flags WHERE id = ?", (new_id,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_all_fraud_flags() -> list[dict]:
    """Fetch every fraud flag, newest first."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM fraud_flags ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------- agents ----------

def check_agent_login(agent_id: str, password_hash: str) -> Optional[dict]:
    """
    Check an agent's credentials.

    NOTE: this compares an already-hashed password against the stored
    password_hash. Hashing/verifying raw passwords (e.g. with bcrypt) is
    intentionally left out of this MVP layer -- do that in the router/
    auth code that calls this function, not here.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM agents WHERE agent_id = ? AND password_hash = ?",
            (agent_id, password_hash),
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()
# ---------- photo paths ----------

def get_all_photo_paths() -> list[str]:
    """Fetch all registered muzzle photo paths for duplicate-photo checking."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT muzzle_photo_path
            FROM animals
            WHERE muzzle_photo_path IS NOT NULL
              AND muzzle_photo_path != ''
            """
        ).fetchall()
        return [row["muzzle_photo_path"] for row in rows]
    finally:
        conn.close()


# Ensure the schema exists as soon as this module is imported. main.py
# (FastAPI) already called init_db() explicitly on its own startup, but
# Streamlit's pages/*.py import `db` directly and never call it -- they'd
# otherwise be left talking to a connection with no tables at all. Doing it
# here, once, guarantees every entry point (FastAPI or any Streamlit page)
# gets the tables created before it can run a query. CREATE TABLE IF NOT
# EXISTS makes this a no-op once the schema is already there.
init_db()

