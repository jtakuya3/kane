#!/usr/bin/env python3
"""
IPO日次チェックスクリプト
docs/ipo_tracking.md の手順に従い、WebSearchとNotion MCPを使って実行される。
このファイルはClaudeエージェントが参照する補助スクリプト（手動実行用）。
実際の毎日自動実行はClaude Code on the webのスケジュールタスクが行う。
"""

import json
from datetime import date, timedelta


def get_check_period() -> tuple[date, date]:
    """チェック対象期間（本日〜3ヶ月後）を返す"""
    today = date.today()
    end = today + timedelta(days=90)
    return today, end


def determine_status(
    today: date,
    listing_date: date | None,
    bb_start: date | None,
    bb_end: date | None,
    offering_price: int | None,
    initial_price: int | None,
) -> str:
    """IPOステータスを判定する"""
    if initial_price and listing_date and listing_date <= today:
        return "上場済"
    if offering_price and listing_date and listing_date > today:
        return "公開価格決定"
    if bb_start and bb_end and bb_start <= today <= bb_end:
        return "BB中"
    return "上場前"


def calculate_return_rate(offering_price: int, initial_price: int) -> str:
    """初値騰落率を計算する"""
    rate = (initial_price - offering_price) / offering_price * 100
    sign = "+" if rate >= 0 else ""
    return f"{sign}{rate:.1f}%"


def assess_attention(
    lead_underwriter: str,
    business: str,
    public_shares: int | None,
) -> str:
    """注目度を判定する"""
    top_underwriters = {"野村證券", "大和証券", "みずほ証券", "SBI証券", "SMBC日興証券"}
    hot_sectors = {"AI", "SaaS", "FinTech", "医療", "DX", "クラウド", "半導体"}

    if lead_underwriter in top_underwriters:
        for sector in hot_sectors:
            if sector in business:
                return "★★★ 高"

    if lead_underwriter in top_underwriters:
        return "★★ 中"

    for sector in hot_sectors:
        if sector in business:
            return "★★ 中"

    return "★ 低"


def format_summary(
    run_date: date,
    ipo_list: list[dict],
    added: int,
    updated: int,
    db_url: str,
) -> str:
    """日次レポートを整形して返す"""
    week_end = run_date + timedelta(days=7)
    this_week = [
        ipo for ipo in ipo_list
        if ipo.get("listing_date") and run_date <= ipo["listing_date"] <= week_end
    ]
    upcoming = [
        ipo for ipo in ipo_list
        if ipo.get("listing_date") and ipo["listing_date"] > week_end
    ]

    lines = [
        f"=== IPO日次チェック完了 ({run_date.strftime('%Y-%m-%d')} 実行) ===",
        "",
        "【今週のIPO（直近7日間）】",
    ]

    if this_week:
        for ipo in sorted(this_week, key=lambda x: x["listing_date"]):
            price_str = f"公開価格:{ipo.get('offering_price', '-')}円" if ipo.get("offering_price") else ""
            lines.append(
                f"- {ipo['listing_date'].strftime('%m/%d')} "
                f"{ipo['name']}（{ipo.get('code', '-')}）"
                f"{ipo.get('market', '')} {price_str} {ipo.get('attention', '-')}"
            )
    else:
        lines.append("- 今週のIPO予定はありません")

    lines += ["", "【来月のIPO予定】"]

    next_month_end = run_date + timedelta(days=60)
    next_month_ipos = [
        ipo for ipo in upcoming
        if ipo.get("listing_date") and ipo["listing_date"] <= next_month_end
    ]

    if next_month_ipos:
        for ipo in sorted(next_month_ipos, key=lambda x: x["listing_date"]):
            low = ipo.get("price_range_low", "-")
            high = ipo.get("price_range_high", "-")
            range_str = f"仮条件:{low}〜{high}円" if low != "-" else ""
            lines.append(
                f"- {ipo['listing_date'].strftime('%m/%d')} "
                f"{ipo['name']}（{ipo.get('code', '-')}）"
                f"{ipo.get('market', '')} {range_str} {ipo.get('attention', '-')}"
            )
    else:
        lines.append("- 来月のIPO予定はありません")

    lines += [
        "",
        "【本日の更新内容】",
        f"- 新規追加: {added}件",
        f"- 情報更新: {updated}件",
        "",
        f"Notionデータベース: {db_url}",
    ]

    return "\n".join(lines)


if __name__ == "__main__":
    today, end = get_check_period()
    print(f"チェック対象期間: {today} 〜 {end}")
    print("このスクリプトは参照用です。実際の実行はClaude Codeスケジュールタスクが行います。")
