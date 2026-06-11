"""Kane — シンプルな研修動画LMS (Learning Management System)。

管理者が研修動画をアップロードし、共有リンクでクライアントに公開できる
最小構成の Flask アプリケーションです。
"""

from kane.app import create_app

__all__ = ["create_app"]
__version__ = "0.1.0"
