"""X post formatter — Generates formatted posts for each agent's decisions."""

from datetime import datetime

from ..agents.decision_engine import Decision
from ..agents.personas import AgentPersona, PERSONA_MAP
from ..portfolio.db import PortfolioSnapshot


def format_daily_brief(fact_sheet_summary: str) -> str:
    """Format the shared daily brief post."""
    now = datetime.now()
    return (
        f"📊 Daily Brief — {now.strftime('%Y/%m/%d')}\n\n"
        f"{fact_sheet_summary}\n\n"
        f"#AIInvestor #5AgentsGame"
    )


def format_decision_post(decision: Decision, persona: AgentPersona, snapshot: PortfolioSnapshot) -> str:
    """Format an agent's investment decision as an X post."""

    action_labels = {
        "buy": "投資判断",
        "sell": "ポジション決済",
        "pass": "見送り判断",
        "watchlist": "ウォッチリスト追加",
    }

    action_label = action_labels.get(decision.action, decision.action)
    ticker_str = f"${decision.ticker}" if decision.ticker else "N/A"

    # Header
    header = f"{persona.emoji} {persona.name} — {action_label}\n\n"

    # Ticker and confidence
    header += f"銘柄：{ticker_str}\n"
    header += f"判断：{decision.action.upper()}\n"
    header += f"確信度：{decision.confidence}%\n\n"

    # Observations
    body = f"【観察した事実】\n{decision.reasoning_observations}\n\n"
    body += f"【{persona.name}の解釈】\n{decision.reasoning_analysis}\n\n"

    # Position details (for buy/sell)
    position_info = ""
    if decision.action == "buy":
        position_info = (
            f"【ポジション】\n"
            f"資金の{decision.position_size_pct:.0f}%投入\n"
            f"損切：-{decision.stop_loss_pct:.0f}%\n"
            f"利確：+{decision.take_profit_pct:.0f}%\n"
        )
        if decision.exit_conditions:
            premise = decision.exit_conditions.get("premise_break", "")
            time_limit = decision.exit_conditions.get("time_limit_days", "")
            if premise:
                position_info += f"前提崩壊条件：{premise}\n"
            if time_limit:
                position_info += f"時間制限：{time_limit}日\n"
        position_info += "\n"

    # Performance
    win_loss = f"{snapshot.wins}勝{snapshot.losses}敗" if (snapshot.wins + snapshot.losses) > 0 else "- / -"
    perf = (
        f"成績：{win_loss}"
        f"（{snapshot.win_rate:.0f}%）\n"
        f"累計リターン：{'+' if snapshot.return_pct >= 0 else ''}{snapshot.return_pct:.1f}%\n"
        f"ポートフォリオ：¥{snapshot.total_value:,.0f}\n"
    )

    # Hashtags
    tags = f"\n#{persona.name}_trades #AIInvestor #5AgentsGame"

    full_post = header + body + position_info + perf + tags

    # X has 280 char limit for regular posts, but we'll use long posts
    # Trim if needed for thread compatibility
    return full_post


def format_weekly_report(snapshots: list[PortfolioSnapshot]) -> str:
    """Format the weekly performance comparison post."""
    now = datetime.now()
    week_num = now.isocalendar()[1]

    lines = [
        f"📈 Week {week_num} Performance — {now.strftime('%Y/%m/%d')}\n",
        f"{'':>10} リターン  勝率    保有数  現金比率",
    ]

    all_positive = True
    best_return = (-999, "")
    for snap in snapshots:
        persona = PERSONA_MAP.get(snap.agent_id)
        if not persona:
            continue

        name = persona.name
        ret = f"{'+' if snap.return_pct >= 0 else ''}{snap.return_pct:.1f}%"
        wl = f"{snap.wins}/{snap.wins + snap.losses}" if (snap.wins + snap.losses) > 0 else "-/-"
        n_pos = len(snap.positions)
        cash_pct = (snap.cash / snap.total_value * 100) if snap.total_value > 0 else 100

        lines.append(f"{name:>5}  {ret:>8}  {wl:>6}  {n_pos}銘柄  {cash_pct:.0f}%")

        if snap.return_pct < 0:
            all_positive = False
        if snap.return_pct > best_return[0]:
            best_return = (snap.return_pct, name)

    status = "全員プラス継続中 ✅" if all_positive else "⚠️ マイナスあり"
    lines.append(f"\n{status}")

    if best_return[1]:
        lines.append(f"\n🏆 今週のトップ：{best_return[1]} ({'+' if best_return[0] >= 0 else ''}{best_return[0]:.1f}%)")

    lines.append("\n#AIInvestor #5AgentsGame #WeeklyReport")

    return "\n".join(lines)


def format_exit_post(
    persona: AgentPersona,
    ticker: str,
    trigger: str,
    entry_price: float,
    exit_price: float,
    quantity: float,
    snapshot: PortfolioSnapshot,
) -> str:
    """Format a position exit (stop loss or take profit) post."""
    pnl_pct = ((exit_price - entry_price) / entry_price) * 100
    pnl_amount = (exit_price - entry_price) * quantity
    invested = entry_price * quantity

    if trigger == "take_profit":
        emoji = "🟢"
        label = "利確売り"
    else:
        emoji = "🔻"
        label = "損切り"

    return (
        f"{emoji} {persona.name} — ポジション決済\n\n"
        f"銘柄：${ticker}\n"
        f"判断：{label}（{'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%）\n\n"
        f"エントリー：¥{entry_price:,.2f}\n"
        f"決済価格：¥{exit_price:,.2f}\n"
        f"損益：{'+' if pnl_amount >= 0 else ''}¥{pnl_amount:,.0f}\n\n"
        f"成績：{snapshot.wins}勝{snapshot.losses}敗（{snapshot.win_rate:.0f}%）\n"
        f"累計リターン：{'+' if snapshot.return_pct >= 0 else ''}{snapshot.return_pct:.1f}%\n"
        f"ポートフォリオ：¥{snapshot.total_value:,.0f}\n\n"
        f"#{persona.name}_trades #AIInvestor #5AgentsGame"
    )
