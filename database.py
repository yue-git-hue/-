"""
数据库模块：SQLite 管理历史开奖数据、用户、选号记录
"""
import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path("./data/lottery.db")


def get_conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS draws (
        issue       TEXT PRIMARY KEY,  -- 期号
        draw_date   TEXT,              -- 开奖日期
        red1 INT, red2 INT, red3 INT, red4 INT, red5 INT, red6 INT,
        blue        INT,
        sales       TEXT,              -- 销售额
        prize_pool  TEXT               -- 奖池
    );

    CREATE TABLE IF NOT EXISTS users (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        username    TEXT UNIQUE NOT NULL,
        created_at  TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS my_picks (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        issue       TEXT,              -- 对应期号（空=未指定）
        red1 INT, red2 INT, red3 INT, red4 INT, red5 INT, red6 INT,
        blue        INT,
        note        TEXT,
        created_at  TEXT DEFAULT (datetime('now','localtime')),
        prize_level INT DEFAULT 0,     -- 中奖等级（0=未中，1-6=等级）
        checked     INT DEFAULT 0      -- 是否已对奖
    );
    """)
    conn.commit()
    conn.close()


def save_draw(issue, date, reds, blue, sales="", prize_pool=""):
    conn = get_conn()
    try:
        conn.execute("""
            INSERT OR IGNORE INTO draws
            (issue,draw_date,red1,red2,red3,red4,red5,red6,blue,sales,prize_pool)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (issue, date, *reds, blue, sales, prize_pool))
        conn.commit()
    finally:
        conn.close()


def get_draws(limit=500):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM draws ORDER BY issue DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_draw():
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM draws ORDER BY issue DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_or_create_user(username: str) -> dict:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE username=?", (username,)
    ).fetchone()
    if not row:
        conn.execute(
            "INSERT INTO users (username) VALUES (?)", (username,)
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM users WHERE username=?", (username,)
        ).fetchone()
    conn.close()
    return dict(row)


def save_pick(user_id, reds, blue, note="", issue=""):
    conn = get_conn()
    conn.execute("""
        INSERT INTO my_picks (user_id,issue,red1,red2,red3,red4,red5,red6,blue,note)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (user_id, issue, *reds, blue, note))
    conn.commit()
    conn.close()


def get_picks(user_id, limit=50):
    conn = get_conn()
    rows = conn.execute("""
        SELECT p.*, d.draw_date,
               d.red1 dr1,d.red2 dr2,d.red3 dr3,d.red4 dr4,d.red5 dr5,d.red6 dr6,
               d.blue dblue
        FROM my_picks p
        LEFT JOIN draws d ON p.issue = d.issue
        WHERE p.user_id=?
        ORDER BY p.created_at DESC LIMIT ?
    """, (user_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_prize(pick_id, level):
    conn = get_conn()
    conn.execute(
        "UPDATE my_picks SET prize_level=?, checked=1 WHERE id=?",
        (level, pick_id)
    )
    conn.commit()
    conn.close()
