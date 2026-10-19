"""symbols.csv の浮動株・発行済株式数の一覧を表示する。

    py -3.11 -m kane.floats
"""
from .config import load_config

LOAN = {"1": "貸借", "0": "信用", "": "未確認"}


def main():
    cfg = load_config("config.toml")
    print(f"{'コード':<6}{'銘柄':<16}{'区分':<10}{'浮動株':>12}{'発行済':>13}{'浮動株比率':>8}{'貸借':>6}")
    for s in cfg.symbols:
        f = f"{s.float_shares:,.0f}" if s.float_shares else "-"
        i = f"{s.issued_shares:,.0f}" if s.issued_shares else "-"
        r = f"{s.float_shares / s.issued_shares:.0%}" if s.float_shares and s.issued_shares else "-"
        print(f"{s.code:<6}{s.name:<16}{s.group:<10}{f:>12}{i:>13}{r:>8}{LOAN.get(s.loan, s.loan):>6}")
    print("※浮動株は推定を含む（大株主からの逆算）。IPOは公開株数＝浮動株。")


if __name__ == "__main__":
    main()
