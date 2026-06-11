"""Kane LMS の Flask アプリケーション本体。

管理者用画面（要ログイン）とクライアント向け共有閲覧画面を提供します。

主な環境変数:
    KANE_ADMIN_PASSWORD   管理画面のログインパスワード（既定: "admin"）
    KANE_SECRET_KEY       セッション署名鍵（本番では必ず設定すること）
    KANE_DB_PATH          SQLite ファイルのパス（既定: instance/kane.db）
    KANE_UPLOAD_DIR       動画保存ディレクトリ（既定: instance/uploads）
    KANE_MAX_UPLOAD_MB    アップロード上限 MB（既定: 2048）
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from kane import db

ALLOWED_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".ogg", ".ogv"}


def _allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def create_app(config: dict | None = None) -> Flask:
    """アプリケーションファクトリ。"""
    app = Flask(__name__, instance_relative_config=True)

    instance_dir = Path(app.instance_path)
    default_db = str(instance_dir / "kane.db")
    default_uploads = str(instance_dir / "uploads")

    app.config.update(
        SECRET_KEY=os.environ.get("KANE_SECRET_KEY", secrets.token_hex(32)),
        ADMIN_PASSWORD=os.environ.get("KANE_ADMIN_PASSWORD", "admin"),
        DB_PATH=os.environ.get("KANE_DB_PATH", default_db),
        UPLOAD_DIR=os.environ.get("KANE_UPLOAD_DIR", default_uploads),
        MAX_CONTENT_LENGTH=int(os.environ.get("KANE_MAX_UPLOAD_MB", "2048"))
        * 1024
        * 1024,
    )
    if config:
        app.config.update(config)

    # ストレージ初期化
    Path(app.config["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["DB_PATH"]).parent.mkdir(parents=True, exist_ok=True)
    db.init_db(app.config["DB_PATH"])

    _register_routes(app)
    return app


# ---- 認証ヘルパー -----------------------------------------------------------

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def _share_is_valid(share) -> bool:
    """共有リンクが有効（未失効）かどうか。"""
    if share is None:
        return False
    if not share["expires_at"]:
        return True
    try:
        expires = datetime.fromisoformat(share["expires_at"])
    except ValueError:
        return True
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) <= expires


def _register_routes(app: Flask) -> None:
    db_path = lambda: app.config["DB_PATH"]  # noqa: E731

    # ---- 認証 ---------------------------------------------------------------

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            password = request.form.get("password", "")
            if secrets.compare_digest(password, app.config["ADMIN_PASSWORD"]):
                session["is_admin"] = True
                nxt = request.args.get("next") or url_for("dashboard")
                return redirect(nxt)
            flash("パスワードが正しくありません。", "error")
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("ログアウトしました。", "success")
        return redirect(url_for("login"))

    # ---- 管理: ダッシュボード -----------------------------------------------

    @app.route("/")
    @login_required
    def dashboard():
        courses = db.list_courses(db_path())
        return render_template("dashboard.html", courses=courses)

    @app.route("/courses", methods=["POST"])
    @login_required
    def create_course():
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        if not title:
            flash("コース名を入力してください。", "error")
            return redirect(url_for("dashboard"))
        course_id = db.create_course(db_path(), title, description)
        flash("コースを作成しました。", "success")
        return redirect(url_for("course_detail", course_id=course_id))

    @app.route("/courses/<int:course_id>/delete", methods=["POST"])
    @login_required
    def delete_course(course_id: int):
        videos = db.list_videos(db_path(), course_id)
        db.delete_course(db_path(), course_id)
        # 紐づく動画ファイルを削除
        for video in videos:
            _remove_file(app, video["filename"])
        flash("コースを削除しました。", "success")
        return redirect(url_for("dashboard"))

    # ---- 管理: コース詳細 ---------------------------------------------------

    @app.route("/courses/<int:course_id>")
    @login_required
    def course_detail(course_id: int):
        course = db.get_course(db_path(), course_id)
        if course is None:
            abort(404)
        videos = db.list_videos(db_path(), course_id)
        shares = db.list_shares(db_path(), course_id)
        return render_template(
            "course.html", course=course, videos=videos, shares=shares
        )

    @app.route("/courses/<int:course_id>/videos", methods=["POST"])
    @login_required
    def upload_video(course_id: int):
        course = db.get_course(db_path(), course_id)
        if course is None:
            abort(404)

        file = request.files.get("video")
        if file is None or file.filename == "":
            flash("動画ファイルを選択してください。", "error")
            return redirect(url_for("course_detail", course_id=course_id))
        if not _allowed_file(file.filename):
            flash(
                "対応していない形式です（mp4, webm, mov, m4v, ogg）。",
                "error",
            )
            return redirect(url_for("course_detail", course_id=course_id))

        title = request.form.get("title", "").strip() or Path(file.filename).stem
        description = request.form.get("description", "").strip()

        # 衝突しない安全なファイル名を生成して保存
        suffix = Path(secure_filename(file.filename)).suffix.lower()
        stored_name = f"{secrets.token_hex(16)}{suffix}"
        dest = Path(app.config["UPLOAD_DIR"]) / stored_name
        file.save(dest)
        size_bytes = dest.stat().st_size

        db.add_video(
            db_path(),
            course_id=course_id,
            title=title,
            filename=stored_name,
            original_name=secure_filename(file.filename),
            content_type=file.mimetype or "video/mp4",
            size_bytes=size_bytes,
            description=description,
        )
        flash("動画をアップロードしました。", "success")
        return redirect(url_for("course_detail", course_id=course_id))

    @app.route(
        "/courses/<int:course_id>/videos/<int:video_id>/delete", methods=["POST"]
    )
    @login_required
    def delete_video(course_id: int, video_id: int):
        row = db.delete_video(db_path(), video_id)
        if row is not None:
            _remove_file(app, row["filename"])
            flash("動画を削除しました。", "success")
        return redirect(url_for("course_detail", course_id=course_id))

    # ---- 管理: 共有リンク ---------------------------------------------------

    @app.route("/courses/<int:course_id>/shares", methods=["POST"])
    @login_required
    def create_share(course_id: int):
        course = db.get_course(db_path(), course_id)
        if course is None:
            abort(404)

        client_name = request.form.get("client_name", "").strip()
        expires_days = request.form.get("expires_days", "").strip()
        expires_at = None
        if expires_days:
            try:
                days = int(expires_days)
                if days > 0:
                    expires_at = (
                        datetime.now(timezone.utc) + timedelta(days=days)
                    ).isoformat()
            except ValueError:
                pass

        token = secrets.token_urlsafe(24)
        db.create_share(db_path(), course_id, token, client_name, expires_at)
        flash("共有リンクを発行しました。", "success")
        return redirect(url_for("course_detail", course_id=course_id))

    @app.route(
        "/courses/<int:course_id>/shares/<int:share_id>/delete", methods=["POST"]
    )
    @login_required
    def delete_share(course_id: int, share_id: int):
        db.delete_share(db_path(), share_id)
        flash("共有リンクを無効化しました。", "success")
        return redirect(url_for("course_detail", course_id=course_id))

    # ---- クライアント向け: 共有閲覧 -----------------------------------------

    @app.route("/share/<token>")
    def share_view(token: str):
        share = db.get_share_by_token(db_path(), token)
        if not _share_is_valid(share):
            abort(404)
        course = db.get_course(db_path(), share["course_id"])
        if course is None:
            abort(404)
        videos = db.list_videos(db_path(), share["course_id"])
        return render_template(
            "share.html", course=course, videos=videos, share=share, token=token
        )

    @app.route("/share/<token>/video/<int:video_id>")
    def share_video_file(token: str, video_id: int):
        share = db.get_share_by_token(db_path(), token)
        if not _share_is_valid(share):
            abort(404)
        video = db.get_video(db_path(), video_id)
        if video is None or video["course_id"] != share["course_id"]:
            abort(404)
        # conditional=True で Range リクエスト（シーク）に対応
        return send_from_directory(
            app.config["UPLOAD_DIR"],
            video["filename"],
            mimetype=video["content_type"],
            conditional=True,
        )

    # ---- ヘルスチェック -----------------------------------------------------

    @app.route("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("404.html"), 404


def _remove_file(app: Flask, filename: str) -> None:
    """アップロードディレクトリ配下のファイルを安全に削除する。"""
    try:
        path = Path(app.config["UPLOAD_DIR"]) / filename
        if path.is_file():
            path.unlink()
    except OSError:
        pass


# `flask --app kane.app run` / `python -m kane.app` 両対応
app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.environ.get("KANE_HOST", "127.0.0.1"),
        port=int(os.environ.get("KANE_PORT", "5000")),
        debug=bool(os.environ.get("KANE_DEBUG")),
    )
