import sqlite3
from contextlib import contextmanager

DB_PATH = "bot.db"

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id    INTEGER PRIMARY KEY,
            username   TEXT,
            full_name  TEXT,
            is_admin   INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS slots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT NOT NULL,
            time        TEXT NOT NULL,
            title       TEXT DEFAULT 'Тренировка',
            max_places  INTEGER DEFAULT 7,
            is_active   INTEGER DEFAULT 1,
            UNIQUE(date, time)
        );
        CREATE TABLE IF NOT EXISTS bookings (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_id    INTEGER NOT NULL REFERENCES slots(id) ON DELETE CASCADE,
            user_id    INTEGER NOT NULL REFERENCES users(user_id),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(slot_id, user_id)
        );
        """)

def upsert_user(user_id: int, username: str | None, full_name: str):
    with get_db() as db:
        db.execute("""
            INSERT INTO users(user_id, username, full_name)
            VALUES(?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                full_name=excluded.full_name
        """, (user_id, username, full_name))

def is_admin(user_id: int) -> bool:
    with get_db() as db:
        row = db.execute("SELECT is_admin FROM users WHERE user_id=?", (user_id,)).fetchone()
        return bool(row and row["is_admin"])

def list_slots():
    with get_db() as db:
        query = """
            SELECT s.*,
                   (SELECT COUNT(*) FROM bookings b WHERE b.slot_id = s.id) AS booked
            FROM slots s
            WHERE s.is_active = 1
        """
        return db.execute(query + " ORDER BY s.date, s.time").fetchall()

def get_slot(slot_id: int):
    with get_db() as db:
        return db.execute("SELECT * FROM slots WHERE id=?", (slot_id,)).fetchone()

def count_bookings(slot_id: int) -> int:
    with get_db() as db:
        return db.execute("SELECT COUNT(*) c FROM bookings WHERE slot_id=?", (slot_id,)).fetchone()["c"]

def add_slot(date: str, time: str, title: str = "Тренировка", max_places: int = 7) -> int:
    with get_db() as db:
        cur = db.execute("INSERT INTO slots(date, time, title, max_places) VALUES(?,?,?,?)",
                         (date, time, title, max_places))
        return cur.lastrowid

def delete_slot(slot_id: int):
    with get_db() as db:
        db.execute("DELETE FROM slots WHERE id=?", (slot_id,))

def update_max_places(slot_id: int, new_max: int):
    with get_db() as db:
        db.execute("UPDATE slots SET max_places=? WHERE id=?", (new_max, slot_id))

def book(slot_id: int, user_id: int) -> tuple[bool, str]:
    slot = get_slot(slot_id)
    if not slot:
        return False, "Слот не найден"
    if count_bookings(slot_id) >= slot["max_places"]:
        return False, "Мест нет"
    with get_db() as db:
        try:
            db.execute("INSERT INTO bookings(slot_id, user_id) VALUES(?,?)", (slot_id, user_id))
        except sqlite3.IntegrityError:
            return False, "Ты уже записан на этот слот"
    return True, "OK"

def unbook(slot_id: int, user_id: int) -> bool:
    with get_db() as db:
        cur = db.execute("DELETE FROM bookings WHERE slot_id=? AND user_id=?", (slot_id, user_id))
        return cur.rowcount > 0

def remove_user_from_slot(slot_id: int, user_id: int) -> bool:
    return unbook(slot_id, user_id)

def user_bookings(user_id: int):
    with get_db() as db:
        return db.execute("""
            SELECT b.id AS booking_id, s.id AS slot_id, s.date, s.time, s.title
            FROM bookings b JOIN slots s ON s.id = b.slot_id
            WHERE b.user_id=? ORDER BY s.date, s.time
        """, (user_id,)).fetchall()

def slot_attendees(slot_id: int):
    with get_db() as db:
        return db.execute("""
            SELECT u.user_id, u.username, u.full_name, b.id as booking_id
            FROM bookings b JOIN users u ON u.user_id = b.user_id
            WHERE b.slot_id=? ORDER BY b.created_at
        """, (slot_id,)).fetchall()