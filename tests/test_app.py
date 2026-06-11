"""Kane LMS のエンドツーエンドに近い機能テスト。"""

import io
import re


def _tiny_mp4() -> bytes:
    """テスト用のダミー動画バイト列（中身は本物の動画でなくてよい）。"""
    return b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64


# ---- 認証 -------------------------------------------------------------------

def test_dashboard_requires_login(client):
    res = client.get("/", follow_redirects=False)
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_login_with_wrong_password(client):
    res = client.post("/login", data={"password": "nope"}, follow_redirects=True)
    assert "パスワードが正しくありません" in res.get_data(as_text=True)


def test_login_success(client):
    res = client.post(
        "/login", data={"password": "test-pass"}, follow_redirects=True
    )
    assert res.status_code == 200
    assert "研修コース一覧" in res.get_data(as_text=True)


def test_healthz(client):
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok"}


# ---- コース＆動画 -----------------------------------------------------------

def _create_course(auth_client, title="新入社員研修"):
    res = auth_client.post(
        "/courses",
        data={"title": title, "description": "説明文"},
        follow_redirects=True,
    )
    assert res.status_code == 200
    match = re.search(r"/courses/(\d+)", res.request.path)
    # follow_redirects 後の最終 URL からコース ID を取得
    assert match, res.request.path
    return int(match.group(1))


def test_create_course(auth_client):
    course_id = _create_course(auth_client)
    res = auth_client.get(f"/courses/{course_id}")
    assert res.status_code == 200
    assert "新入社員研修" in res.get_data(as_text=True)


def test_upload_video(auth_client):
    course_id = _create_course(auth_client)
    data = {
        "title": "第1章 オリエンテーション",
        "video": (io.BytesIO(_tiny_mp4()), "lesson1.mp4"),
    }
    res = auth_client.post(
        f"/courses/{course_id}/videos",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert "動画をアップロードしました" in body
    assert "第1章 オリエンテーション" in body


def test_reject_non_video_extension(auth_client):
    course_id = _create_course(auth_client)
    data = {"video": (io.BytesIO(b"hello"), "notes.txt")}
    res = auth_client.post(
        f"/courses/{course_id}/videos",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert "対応していない形式です" in res.get_data(as_text=True)


# ---- 共有リンク（クライアント視点） -----------------------------------------

def _make_share(auth_client, course_id):
    auth_client.post(
        f"/courses/{course_id}/shares",
        data={"client_name": "テスト株式会社"},
        follow_redirects=True,
    )
    res = auth_client.get(f"/courses/{course_id}")
    body = res.get_data(as_text=True)
    token = re.search(r"/share/([A-Za-z0-9_\-]+)", body).group(1)
    return token


def test_share_link_lets_client_view_without_login(auth_client, app):
    course_id = _create_course(auth_client)
    auth_client.post(
        f"/courses/{course_id}/videos",
        data={"title": "公開動画", "video": (io.BytesIO(_tiny_mp4()), "v.mp4")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    token = _make_share(auth_client, course_id)

    # 未ログインの新しいクライアントでアクセス
    anon = app.test_client()
    res = anon.get(f"/share/{token}")
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert "公開動画" in body
    assert "新入社員研修" in body


def test_share_video_streaming_supports_range(auth_client, app):
    course_id = _create_course(auth_client)
    auth_client.post(
        f"/courses/{course_id}/videos",
        data={"title": "動画", "video": (io.BytesIO(_tiny_mp4()), "v.mp4")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    token = _make_share(auth_client, course_id)
    res = auth_client.get(f"/share/{token}")
    body = res.get_data(as_text=True)
    video_url = re.search(r'src="(/share/[^"]+/video/\d+)"', body).group(1)

    anon = app.test_client()
    # Range リクエストで部分応答 (206) が返ること
    res = anon.get(video_url, headers={"Range": "bytes=0-7"})
    assert res.status_code == 206
    assert res.headers.get("Accept-Ranges") == "bytes"


def test_invalid_token_returns_404(client):
    res = client.get("/share/does-not-exist")
    assert res.status_code == 404
