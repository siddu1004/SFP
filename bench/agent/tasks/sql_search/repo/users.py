"""User lookup for the admin page."""
import sqlite3


def connect(path=":memory:"):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)")
    return conn


def search_users(conn, name_prefix, limit=20):
    """Users whose name starts with name_prefix, by name."""
    cur = conn.execute(
        f"SELECT id, name, email FROM users WHERE name LIKE '{name_prefix}%' ORDER BY name LIMIT {limit}")
    return [dict(id=r[0], name=r[1], email=r[2]) for r in cur.fetchall()]
