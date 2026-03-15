"""Decision engine — Connects data to agent judgment via Claude API."""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime

import anthropic

from ..portfolio.db import PortfolioDB, PortfolioSnapshot
from .personas import AgentPersona

logger = logging.getLogger(__name__)


@dataclass
class Decision:
    agent_id: str
    action: str  # buy, sell, pass, watchlist
    ticker: str | None
    confidence: float
    reasoning_observations: str  # 観察した事実
    reasoning_analysis: str  # 自分の解釈
    position_size_pct: float | None  # 資金の何%
    stop_loss_pct: float | None
    take_profit_pct: float | None
    exit_conditions: dict | None  # 前提崩壊条件、時間制限など
    raw_response: str


DECISION_OUTPUT_SCHEMA = """
あなたの判断を以下のJSON形式で出力してください。JSONのみ出力し、他のテキストは不要です。

{
    "action": "buy" | "sell" | "pass" | "watchlist",
    "ticker": "銘柄シンボル（例: NVDA, AAPL）。passの場合は最も検討した銘柄",
    "confidence": 0-100の整数,
    "observations": "観察した事実を箇条書き。解釈を混ぜない",
    "analysis": "あなたの哲学に基づく解釈。なぜこの判断に至ったか",
    "position_size_pct": 0-35の整数（資金の何%を投入するか。pass/watchlistは0）,
    "stop_loss_pct": 0-20の整数（何%下落で損切りか）,
    "take_profit_pct": 0-50の整数（何%上昇で利確か）,
    "exit_conditions": {
        "premise_break": "この前提が崩れたら即撤退する条件",
        "time_limit_days": 再評価するまでの日数,
        "other": "その他の撤退条件"
    }
}
"""


class DecisionEngine:
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.db = PortfolioDB()

    def make_decision(
        self,
        persona: AgentPersona,
        fact_sheet: str,
        portfolio: PortfolioSnapshot,
        other_agents_decisions: list[Decision] | None = None,
    ) -> Decision:
        """Have an agent make an investment decision based on current data."""

        # Build context about other agents' decisions (if available)
        others_context = ""
        if other_agents_decisions:
            others_lines = []
            for d in other_agents_decisions:
                others_lines.append(
                    f"- {d.agent_id.upper()}: {d.action} {d.ticker or 'N/A'} "
                    f"(確信度{d.confidence}%)"
                )
            others_context = f"""
## 他のエージェントの判断（参考）
{chr(10).join(others_lines)}

注意: 全員が同じ方向なら何か見落としている可能性がある。
"""

        # Build portfolio context
        positions_text = "なし"
        if portfolio.positions:
            pos_lines = []
            for p in portfolio.positions:
                sign = "+" if p["pnl_pct"] >= 0 else ""
                pos_lines.append(
                    f"- {p['ticker']}: {sign}{p['pnl_pct']:.1f}% "
                    f"(エントリー{p['entry_price']:.2f} → 現在{p['current_price']:.2f}) "
                    f"SL:{p['stop_loss']:.2f} TP:{p['take_profit']:.2f}"
                )
            positions_text = "\n".join(pos_lines)

        portfolio_context = f"""
## あなたのポートフォリオ状況
- 現金: ¥{portfolio.cash:,.0f}
- ポジション評価額: ¥{portfolio.positions_value:,.0f}
- 総資産: ¥{portfolio.total_value:,.0f} ({'+' if portfolio.return_pct >= 0 else ''}{portfolio.return_pct:.1f}%)
- 勝率: {portfolio.wins}勝{portfolio.losses}敗 ({portfolio.win_rate:.0f}%)

### 保有ポジション
{positions_text}
"""

        user_message = f"""
現在時刻: {datetime.now().strftime('%Y/%m/%d %H:%M')} JST

{fact_sheet}

{portfolio_context}

{others_context}

## あなたの任務
1. 【観察フェーズ】上記の情報から重要な事実をピックアップせよ。まだ判断するな。
2. 【分析フェーズ】あなたの投資哲学に基づいて解釈せよ。まだ判断するな。
3. 【判断フェーズ】確信度を計算し、あなたのルールに照らして判断せよ。

重要:
- 既存ポジションが損切り/利確ラインに達していたら、sellを優先
- 確信度が基準未満なら「pass」か「watchlist」にせよ。無理に投資するな
- 「投資しない」は恥ではない。最良の判断であることもある

{DECISION_OUTPUT_SCHEMA}
"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                system=persona.system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

            raw = response.content[0].text.strip()
            # Extract JSON from response
            json_str = raw
            if "```json" in raw:
                json_str = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                json_str = raw.split("```")[1].split("```")[0].strip()

            data = json.loads(json_str)

            return Decision(
                agent_id=persona.agent_id,
                action=data.get("action", "pass"),
                ticker=data.get("ticker"),
                confidence=data.get("confidence", 0),
                reasoning_observations=data.get("observations", ""),
                reasoning_analysis=data.get("analysis", ""),
                position_size_pct=data.get("position_size_pct", 0),
                stop_loss_pct=data.get("stop_loss_pct", persona.default_stop_loss_pct * 100),
                take_profit_pct=data.get("take_profit_pct", persona.default_take_profit_pct * 100),
                exit_conditions=data.get("exit_conditions", {}),
                raw_response=raw,
            )

        except Exception as e:
            logger.error(f"Decision engine error for {persona.agent_id}: {e}")
            return Decision(
                agent_id=persona.agent_id,
                action="pass",
                ticker=None,
                confidence=0,
                reasoning_observations=f"Error: {e}",
                reasoning_analysis="システムエラーにより判断不能。安全のため見送り。",
                position_size_pct=0,
                stop_loss_pct=None,
                take_profit_pct=None,
                exit_conditions=None,
                raw_response=str(e),
            )

    def check_stop_loss_take_profit(
        self, agent_id: str, current_prices: dict[str, float]
    ) -> list[dict]:
        """Check all open positions for stop loss / take profit triggers."""
        triggers = []
        positions = self.db.get_open_positions(agent_id)

        for pos in positions:
            ticker = pos["ticker"]
            current_price = current_prices.get(ticker)
            if current_price is None:
                continue

            if current_price <= pos["stop_loss_price"]:
                triggers.append({
                    "position_id": pos["id"],
                    "ticker": ticker,
                    "trigger": "stop_loss",
                    "entry_price": pos["entry_price"],
                    "trigger_price": pos["stop_loss_price"],
                    "current_price": current_price,
                    "pnl_pct": ((current_price - pos["entry_price"]) / pos["entry_price"]) * 100,
                })
            elif current_price >= pos["take_profit_price"]:
                triggers.append({
                    "position_id": pos["id"],
                    "ticker": ticker,
                    "trigger": "take_profit",
                    "entry_price": pos["entry_price"],
                    "trigger_price": pos["take_profit_price"],
                    "current_price": current_price,
                    "pnl_pct": ((current_price - pos["entry_price"]) / pos["entry_price"]) * 100,
                })

        return triggers
