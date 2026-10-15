"""固定監視銘柄（symbols.csv）の乖離ラインをまとめて表示する。

    py -3.11 -m kane.line_watch
"""
from .line import main

if __name__ == "__main__":
    main(default_codes=True)
