"""Stocarea produselor și a istoricului de prețuri în SQLite."""

import csv
import sqlite3
from datetime import datetime

DB_FILE = "prices.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    url          TEXT UNIQUE NOT NULL,
    name         TEXT,
    target_price REAL,              -- pragul de alertă (poate lipsi)
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prices (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    price      REAL NOT NULL,
    currency   TEXT NOT NULL,
    available  INTEGER NOT NULL,
    checked_at TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def connect(path: str = DB_FILE) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def add_product(conn, url, name, target_price=None) -> int:
    cur = conn.execute(
        "INSERT INTO products (url, name, target_price, created_at) VALUES (?, ?, ?, ?)",
        (url, name, target_price, now()),
    )
    conn.commit()
    return cur.lastrowid


def remove_product(conn, product_id) -> bool:
    cur = conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    return cur.rowcount > 0


def get_product(conn, product_id):
    return conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()


def list_products(conn):
    """Produsele, fiecare cu ultimul preț înregistrat."""
    return conn.execute(
        """
        SELECT p.*,
               (SELECT price FROM prices WHERE product_id = p.id
                ORDER BY checked_at DESC, id DESC LIMIT 1) AS last_price,
               (SELECT MIN(price) FROM prices WHERE product_id = p.id) AS min_price
        FROM products p ORDER BY p.id
        """
    ).fetchall()


def last_price(conn, product_id):
    row = conn.execute(
        "SELECT price FROM prices WHERE product_id = ? ORDER BY checked_at DESC, id DESC LIMIT 1",
        (product_id,),
    ).fetchone()
    return row["price"] if row else None


def add_price(conn, product_id, price, currency, available):
    conn.execute(
        "INSERT INTO prices (product_id, price, currency, available, checked_at) VALUES (?, ?, ?, ?, ?)",
        (product_id, price, currency, int(available), now()),
    )
    conn.commit()


def history(conn, product_id):
    return conn.execute(
        "SELECT price, currency, available, checked_at FROM prices "
        "WHERE product_id = ? ORDER BY checked_at, id",
        (product_id,),
    ).fetchall()


def export_csv(conn, path) -> int:
    rows = conn.execute(
        """
        SELECT p.id, p.name, p.url, pr.price, pr.currency, pr.available, pr.checked_at
        FROM prices pr JOIN products p ON p.id = pr.product_id
        ORDER BY p.id, pr.checked_at
        """
    ).fetchall()
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id_produs", "nume", "url", "pret", "moneda", "in_stoc", "data"])
        writer.writerows(tuple(r) for r in rows)
    return len(rows)
