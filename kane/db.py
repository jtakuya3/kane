"""SQLite を使ったデータアクセス層。

標準ライブラリの sqlite3 のみを使用し、外部 ORM には依存しません。
コース（研修コース）・動画（レッスン）・共有リンクの3テーブルを管理します。
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS courses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS videos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id     INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title         TEXT    NOT NULL,
    description   TEXT    NOT NULL DEFAULT '',
    filename      TEXT    NOT NULL,
    original_name TEXT    NOT NULL DEFAULT '',
    content_type  TEXT    NOT NULL DEFAULT 'video/mp4',
    size_bytes    INTEGER NOT NULL DEFAULT 0,
    position      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS shares (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id   INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    token       TEXT    NOT NULL UNIQUE,
    client_name TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL,
    expires_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_videos_course ON videos(course_id);
CREATE INDEX IF NOT EXISTS idx_shares_course ON shares(course_id);
CREATE INDEX IF NOT EXISTS idx_shares_token  ON shares(token);
"""


def utcnow() -> str:
    """現在時刻を ISO8601 (UTC) 文字列で返す。"""
    return datetime.now(timezone.utc).isoformat()


def get_connection(db_path: str) -> sqlite3.Connection:
    """行を辞書ライクに扱える接続を返す。外部キー制約も有効化する。"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str) -> None:
    """スキーマを作成する（存在しなければ）。"""
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def connection(db_path: str) -> Iterator[sqlite3.Connection]:
    """with 文で使う接続コンテキスト。正常終了時にコミットする。"""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---- コース -----------------------------------------------------------------

def create_course(db_path: str, title: str, description: str = "") -> int:
    with connection(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO courses (title, description, created_at) VALUES (?, ?, ?)",
            (title, description, utcnow()),
        )
        return int(cur.lastrowid)


def list_courses(db_path: str) -> list[sqlite3.Row]:
    with connection(db_path) as conn:
        return conn.execute(
            """
            SELECT c.*,
                   (SELECT COUNT(*) FROM videos v WHERE v.course_id = c.id) AS video_count,
                   (SELECT COUNT(*) FROM shares s WHERE s.course_id = c.id) AS share_count
            FROM courses c
            ORDER BY c.created_at DESC
            """
        ).fetchall()


def get_course(db_path: str, course_id: int) -> Optional[sqlite3.Row]:
    with connection(db_path) as conn:
        return conn.execute(
            "SELECT * FROM courses WHERE id = ?", (course_id,)
        ).fetchone()


def delete_course(db_path: str, course_id: int) -> None:
    with connection(db_path) as conn:
        conn.execute("DELETE FROM courses WHERE id = ?", (course_id,))


# ---- 動画 -------------------------------------------------------------------

def add_video(
    db_path: str,
    course_id: int,
    title: str,
    filename: str,
    original_name: str = "",
    content_type: str = "video/mp4",
    size_bytes: int = 0,
    description: str = "",
) -> int:
    with connection(db_path) as conn:
        next_pos = conn.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 FROM videos WHERE course_id = ?",
            (course_id,),
        ).fetchone()[0]
        cur = conn.execute(
            """
            INSERT INTO videos
                (course_id, title, description, filename, original_name,
                 content_type, size_bytes, position, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                course_id,
                title,
                description,
                filename,
                original_name,
                content_type,
                size_bytes,
                next_pos,
                utcnow(),
            ),
        )
        return int(cur.lastrowid)


def list_videos(db_path: str, course_id: int) -> list[sqlite3.Row]:
    with connection(db_path) as conn:
        return conn.execute(
            "SELECT * FROM videos WHERE course_id = ? ORDER BY position, id",
            (course_id,),
        ).fetchall()


def get_video(db_path: str, video_id: int) -> Optional[sqlite3.Row]:
    with connection(db_path) as conn:
        return conn.execute(
            "SELECT * FROM videos WHERE id = ?", (video_id,)
        ).fetchone()


def delete_video(db_path: str, video_id: int) -> Optional[sqlite3.Row]:
    """動画レコードを削除し、削除したレコード（ファイル削除用）を返す。"""
    with connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM videos WHERE id = ?", (video_id,)
        ).fetchone()
        if row is not None:
            conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        return row


# ---- 共有リンク -------------------------------------------------------------

def create_share(
    db_path: str,
    course_id: int,
    token: str,
    client_name: str = "",
    expires_at: Optional[str] = None,
) -> int:
    with connection(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO shares (course_id, token, client_name, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (course_id, token, client_name, utcnow(), expires_at),
        )
        return int(cur.lastrowid)


def list_shares(db_path: str, course_id: int) -> list[sqlite3.Row]:
    with connection(db_path) as conn:
        return conn.execute(
            "SELECT * FROM shares WHERE course_id = ? ORDER BY created_at DESC",
            (course_id,),
        ).fetchall()


def get_share_by_token(db_path: str, token: str) -> Optional[sqlite3.Row]:
    with connection(db_path) as conn:
        return conn.execute(
            "SELECT * FROM shares WHERE token = ?", (token,)
        ).fetchone()


def delete_share(db_path: str, share_id: int) -> None:
    with connection(db_path) as conn:
        conn.execute("DELETE FROM shares WHERE id = ?", (share_id,))
