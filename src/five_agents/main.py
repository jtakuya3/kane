"""Main orchestrator — Runs the 5 agent investment cycle."""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from .agents.decision_engine import Decision, DecisionEngine
from .agents.personas import ALL_PERSONAS, PERSONA_MAP
from .data.registry import build_shared_fact_sheet, registry
from .data.sources.loader import register_all_sources
from .portfolio.db import PortfolioDB
from .posting.formatter import (
    format_daily_brief,
    format_decision_post,
    format_exit_post,
    format_weekly_report,
)
from .posting.x_client import XClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def run_daily_cycle(dry_run: bool = True):
    """Run one complete daily cycle for all 5 agents."""
    logger.info("=" * 60)
    logger.info("Starting daily investment cycle")
    logger.info("=" * 60)

    # 1. Initialize
    db = PortfolioDB()
    engine = DecisionEngine()
    x_client = XClient(dry_run=dry_run)

    # 2. Fetch all data
    logger.info("Fetching data from all sources...")
    data_points = await registry.fetch_all()
    fact_sheet = build_shared_fact_sheet(data_points)

    logger.info(f"Fact sheet generated ({len(data_points)} data points)")

    # 3. Extract current prices for portfolio valuation
    current_prices = {}
    for dp in data_points:
        if dp.source == "yahoo_finance" and dp.relevance_tickers:
            ticker = dp.relevance_tickers[0]
            price = dp.metadata.get("close")
            if price:
                current_prices[ticker] = price

    # 4. Post daily brief
    brief_summary = _summarize_for_brief(data_points)
    brief_post = format_daily_brief(brief_summary)
    x_client.post(brief_post)

    # 5. Check stop loss / take profit for all agents
    for persona in ALL_PERSONAS:
        triggers = engine.check_stop_loss_take_profit(persona.agent_id, current_prices)
        for trigger in triggers:
            logger.info(
                f"🚨 {persona.name}: {trigger['trigger']} triggered for "
                f"{trigger['ticker']} ({trigger['pnl_pct']:+.1f}%)"
            )
            db.close_position(
                trigger["position_id"],
                trigger["current_price"],
                trigger["trigger"],
            )
            snapshot = db.get_snapshot(persona.agent_id, current_prices)
            exit_post = format_exit_post(
                persona,
                trigger["ticker"],
                trigger["trigger"],
                trigger["entry_price"],
                trigger["current_price"],
                0,  # quantity from position
                snapshot,
            )
            x_client.post(exit_post)

    # 6. Each agent makes a decision (sequentially so they can see others' decisions)
    decisions: list[Decision] = []

    for persona in ALL_PERSONAS:
        logger.info(f"\n{'─'*40}")
        logger.info(f"Agent {persona.name} analyzing...")

        snapshot = db.get_snapshot(persona.agent_id, current_prices)

        decision = engine.make_decision(
            persona=persona,
            fact_sheet=fact_sheet,
            portfolio=snapshot,
            other_agents_decisions=decisions,  # Previous agents' decisions
        )

        decisions.append(decision)

        logger.info(
            f"{persona.name}: {decision.action} {decision.ticker or 'N/A'} "
            f"(confidence: {decision.confidence}%)"
        )

        # Execute the decision
        if decision.action == "buy" and decision.ticker and decision.position_size_pct:
            _execute_buy(db, persona, decision, snapshot, current_prices)
        elif decision.action == "pass":
            if decision.ticker:
                db.record_pass(persona.agent_id, decision.ticker, decision.confidence, decision.reasoning_analysis)
        elif decision.action == "watchlist":
            if decision.ticker:
                db.record_watchlist(persona.agent_id, decision.ticker, decision.confidence, decision.reasoning_analysis)

        # Post decision
        updated_snapshot = db.get_snapshot(persona.agent_id, current_prices)
        post = format_decision_post(decision, persona, updated_snapshot)
        x_client.post(post)

    # 7. Check if it's Sunday → post weekly report
    if datetime.now().weekday() == 6:
        snapshots = [db.get_snapshot(p.agent_id, current_prices) for p in ALL_PERSONAS]
        report = format_weekly_report(snapshots)
        x_client.post(report)

    # 8. Correlation check — warn if all agents agree
    buy_agents = [d for d in decisions if d.action == "buy"]
    if len(buy_agents) >= 4:
        same_ticker = len(set(d.ticker for d in buy_agents)) == 1
        if same_ticker:
            logger.warning(
                "⚠️ CORRELATION ALERT: 4+ agents buying the same ticker! "
                "This may indicate groupthink or a market trap."
            )
            x_client.post(
                "⚠️ 相関アラート\n\n"
                f"4人以上のエージェントが同じ銘柄 ${buy_agents[0].ticker} を買い判断。\n"
                "全員一致 = 何か見落としている可能性。慎重に。\n\n"
                "#AIInvestor #5AgentsGame"
            )

    logger.info("\n" + "=" * 60)
    logger.info("Daily cycle complete")
    logger.info("=" * 60)


def _execute_buy(db, persona, decision, snapshot, current_prices):
    """Execute a buy decision."""
    from .portfolio.db import Position

    ticker = decision.ticker
    price = current_prices.get(ticker)
    if not price:
        logger.warning(f"No price available for {ticker}, skipping buy")
        return

    # Calculate position size
    invest_amount = snapshot.cash * (decision.position_size_pct / 100)
    quantity = invest_amount / price

    # Calculate stop loss and take profit prices
    stop_loss_price = price * (1 - decision.stop_loss_pct / 100)
    take_profit_price = price * (1 + decision.take_profit_pct / 100)

    import json

    pos = Position(
        id=None,
        agent_id=persona.agent_id,
        ticker=ticker,
        entry_price=price,
        quantity=quantity,
        entry_date=datetime.now().isoformat(),
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
        exit_conditions=json.dumps(decision.exit_conditions or {}),
        confidence=decision.confidence,
        reasoning=decision.reasoning_analysis,
    )

    pos_id = db.open_position(pos)
    logger.info(
        f"Opened position #{pos_id}: {ticker} @ {price:.2f} "
        f"qty={quantity:.4f} SL={stop_loss_price:.2f} TP={take_profit_price:.2f}"
    )


def _summarize_for_brief(data_points) -> str:
    """Create a concise summary for the daily brief post."""
    lines = []

    # Market data
    market_points = [dp for dp in data_points if dp.source == "yahoo_finance"]
    key_indices = ["^GSPC", "^N225", "^VIX", "BTC-USD"]
    for dp in market_points:
        if dp.relevance_tickers and dp.relevance_tickers[0] in key_indices:
            lines.append(f"・{dp.title}: {dp.content}")

    # Fear & Greed
    fg = [dp for dp in data_points if dp.source == "fear_greed"]
    if fg:
        lines.append(f"・{fg[0].content}")

    # Top news
    news = [dp for dp in data_points if dp.source == "gdelt"]
    if news:
        lines.append(f"\n[注目ニュース]")
        for n in news[:3]:
            lines.append(f"・{n.title[:60]}")

    return "\n".join(lines) if lines else "データ取得中..."


def main():
    """Entry point."""
    load_dotenv()

    # Register all data sources
    register_all_sources()

    # Check for dry-run flag
    dry_run = "--live" not in sys.argv

    if dry_run:
        logger.info("Running in DRY RUN mode (use --live to post to X)")
    else:
        logger.info("Running in LIVE mode — posts will be sent to X")

    asyncio.run(run_daily_cycle(dry_run=dry_run))


if __name__ == "__main__":
    main()
