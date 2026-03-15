"""Notification system — Discord / LINE / console alerts for important events."""

import logging
import os
from enum import Enum

import requests

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    INFO = "info"  # 日次サマリー、見送り判断
    ACTION = "action"  # 買い/売り判断
    URGENT = "urgent"  # 損切り/利確トリガー、相関アラート


class Notifier:
    """Sends notifications via Discord webhook and/or LINE Notify."""

    def __init__(self):
        self.discord_url = os.environ.get("DISCORD_WEBHOOK_URL")
        self.line_token = os.environ.get("LINE_NOTIFY_TOKEN")

    def notify(self, title: str, body: str, level: AlertLevel = AlertLevel.INFO):
        """Send notification to all configured channels."""
        logger.info(f"[NOTIFY:{level.value}] {title}")

        if self.discord_url:
            self._send_discord(title, body, level)

        if self.line_token:
            self._send_line(title, body, level)

        if not self.discord_url and not self.line_token:
            logger.info(f"[CONSOLE NOTIFY] {title}\n{body}")

    def _send_discord(self, title: str, body: str, level: AlertLevel):
        color_map = {
            AlertLevel.INFO: 0x808080,  # gray
            AlertLevel.ACTION: 0x00FF00,  # green
            AlertLevel.URGENT: 0xFF0000,  # red
        }

        payload = {
            "embeds": [{
                "title": title,
                "description": body[:4000],
                "color": color_map.get(level, 0x808080),
            }]
        }

        try:
            resp = requests.post(self.discord_url, json=payload, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Discord notification failed: {e}")

    def _send_line(self, title: str, body: str, level: AlertLevel):
        prefix = {"urgent": "🚨", "action": "📈", "info": "📊"}.get(level.value, "")
        message = f"\n{prefix} {title}\n\n{body[:900]}"

        try:
            resp = requests.post(
                "https://notify-api.line.me/api/notify",
                headers={"Authorization": f"Bearer {self.line_token}"},
                data={"message": message},
                timeout=10,
            )
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"LINE notification failed: {e}")


# Convenience functions
_notifier = None


def get_notifier() -> Notifier:
    global _notifier
    if _notifier is None:
        _notifier = Notifier()
    return _notifier


def notify_daily_summary(summary: str):
    get_notifier().notify("📊 Daily Brief", summary, AlertLevel.INFO)


def notify_trade(agent_name: str, action: str, ticker: str, confidence: int, reasoning: str):
    title = f"📈 {agent_name}: {action.upper()} ${ticker}"
    body = f"確信度: {confidence}%\n\n{reasoning[:500]}"
    get_notifier().notify(title, body, AlertLevel.ACTION)


def notify_exit(agent_name: str, ticker: str, trigger: str, pnl_pct: float):
    emoji = "🟢" if pnl_pct >= 0 else "🔻"
    trigger_label = "利確" if trigger == "take_profit" else "損切り"
    title = f"{emoji} {agent_name}: {trigger_label} ${ticker} ({pnl_pct:+.1f}%)"
    body = f"ポジション決済: {trigger_label}\n損益: {pnl_pct:+.1f}%"
    get_notifier().notify(title, body, AlertLevel.URGENT)


def notify_correlation_alert(ticker: str, agents: list[str]):
    title = f"⚠️ 相関アラート: ${ticker}"
    body = f"{', '.join(agents)} が全員同じ方向。何か見落としている可能性。"
    get_notifier().notify(title, body, AlertLevel.URGENT)


def notify_weekly_report(report: str):
    get_notifier().notify("📈 Weekly Report", report, AlertLevel.INFO)
