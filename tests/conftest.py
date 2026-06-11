"""pytest フィクスチャ。各テストを隔離された一時ディレクトリ上で実行する。"""

import pytest

from kane.app import create_app


@pytest.fixture()
def app(tmp_path):
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "ADMIN_PASSWORD": "test-pass",
            "DB_PATH": str(tmp_path / "test.db"),
            "UPLOAD_DIR": str(tmp_path / "uploads"),
            "WTF_CSRF_ENABLED": False,
        }
    )
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_client(client):
    """ログイン済みの管理者クライアント。"""
    client.post("/login", data={"password": "test-pass"})
    return client
