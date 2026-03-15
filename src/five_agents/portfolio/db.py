"""Portfolio management with SQLite. Tracks positions, trades, and performance."""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "portfolio.db"

INITIAL_CAPITAL = 1_000_000  # 100万円


@dataclass
class Position:
    id: int | None
    agent_id: str
    ticker: str
    entry_price: float
    quantity: float
    entry_date: str
    stop_loss_price: float
    take_profit_price: float
    exit_conditions: str  # JSON string
    confidence: float
    reasoning: str
    status: str = "open"  # open, closed, stopped_out
    exit_price: float | None = None
    exit_date: str | None = None
    exit_reason: str | None = None


@dataclass
class TradeRecord:
    agent_id: str
    ticker: str
    action: str  # buy, sell, pass, watchlist
    price: float | None
    amount: float | None
    confidence: float
    reasoning: str
    timestamp: str


@dataclass
class PortfolioSnapshot:
    agent_id: str
    cash: float
    positions_value: float
    total_value: float
    return_pct: float
    wins: int
    losses: int
    win_rate: float
    positions: list[dict]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            entry_price REAL NOT NULL,
            quantity REAL NOT NULL,
            entry_date TEXT NOT NULL,
            stop_loss_price REAL NOT NULL,
            take_profit_price REAL NOT NULL,
            exit_conditions TEXT DEFAULT '{}',
            confidence REAL NOT NULL,
            reasoning TEXT NOT NULL,
            status TEXT DEFAULT 'open',
            exit_price REAL,
            exit_date TEXT,
            exit_reason TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            action TEXT NOT NULL,
            price REAL,
            amount REAL,
            confidence REAL NOT NULL,
            reasoning TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS agent_cash (
            agent_id TEXT PRIMARY KEY,
            cash REAL NOT NULL
        )
    """)

    # Initialize cash for all agents
    for agent_id in ["elon", "dario", "steve", "peter", "jeff"]:
        c.execute(
            "INSERT OR IGNORE INTO agent_cash (agent_id, cash) VALUES (?, ?)",
            (agent_id, INITIAL_CAPITAL),
        )

    conn.commit()
    conn.close()


class PortfolioDB:
    def __init__(self):
        init_db()
        self.db_path = DB_PATH

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_cash(self, agent_id: str) -> float:
        conn = self._conn()
        row = conn.execute(
            "SELECT cash FROM agent_cash WHERE agent_id = ?", (agent_id,)
        ).fetchone()
        conn.close()
        return row["cash"] if row else INITIAL_CAPITAL

    def open_position(self, pos: Position) -> int:
        conn = self._conn()
        cost = pos.entry_price * pos.quantity

        # Deduct cash
        conn.execute(
            "UPDATE agent_cash SET cash = cash - ? WHERE agent_id = ?",
            (cost, pos.agent_id),
        )

        cursor = conn.execute(
            """INSERT INTO positions
            (agent_id, ticker, entry_price, quantity, entry_date,
             stop_loss_price, take_profit_price, exit_conditions,
             confidence, reasoning, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')""",
            (
                pos.agent_id, pos.ticker, pos.entry_price, pos.quantity,
                pos.entry_date, pos.stop_loss_price, pos.take_profit_price,
                pos.exit_conditions, pos.confidence, pos.reasoning,
            ),
        )

        # Record trade
        conn.execute(
            """INSERT INTO trades
            (agent_id, ticker, action, price, amount, confidence, reasoning, timestamp)
            VALUES (?, ?, 'buy', ?, ?, ?, ?, ?)""",
            (
                pos.agent_id, pos.ticker, pos.entry_price, cost,
                pos.confidence, pos.reasoning, pos.entry_date,
            ),
        )

        conn.commit()
        pos_id = cursor.lastrowid
        conn.close()
        return pos_id

    def close_position(self, position_id: int, exit_price: float, exit_reason: str):
        conn = self._conn()
        pos = conn.execute(
            "SELECT * FROM positions WHERE id = ?", (position_id,)
        ).fetchone()

        if not pos:
            conn.close()
            return

        proceeds = exit_price * pos["quantity"]
        now = datetime.now().isoformat()

        conn.execute(
            """UPDATE positions SET status = 'closed', exit_price = ?,
            exit_date = ?, exit_reason = ? WHERE id = ?""",
            (exit_price, now, exit_reason, position_id),
        )

        conn.execute(
            "UPDATE agent_cash SET cash = cash + ? WHERE agent_id = ?",
            (proceeds, pos["agent_id"]),
        )

        conn.execute(
            """INSERT INTO trades
            (agent_id, ticker, action, price, amount, confidence, reasoning, timestamp)
            VALUES (?, ?, 'sell', ?, ?, ?, ?, ?)""",
            (
                pos["agent_id"], pos["ticker"], exit_price, proceeds,
                pos["confidence"], exit_reason, now,
            ),
        )

        conn.commit()
        conn.close()

    def get_open_positions(self, agent_id: str) -> list[dict]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM positions WHERE agent_id = ? AND status = 'open'",
            (agent_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_closed_positions(self, agent_id: str) -> list[dict]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM positions WHERE agent_id = ? AND status != 'open'",
            (agent_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def record_pass(self, agent_id: str, ticker: str, confidence: float, reasoning: str):
        """Record a 'pass' decision (chose not to invest)."""
        conn = self._conn()
        conn.execute(
            """INSERT INTO trades
            (agent_id, ticker, action, price, amount, confidence, reasoning, timestamp)
            VALUES (?, ?, 'pass', NULL, NULL, ?, ?, ?)""",
            (agent_id, ticker, confidence, reasoning, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()

    def record_watchlist(self, agent_id: str, ticker: str, confidence: float, reasoning: str):
        """Record a 'watchlist' decision."""
        conn = self._conn()
        conn.execute(
            """INSERT INTO trades
            (agent_id, ticker, action, price, amount, confidence, reasoning, timestamp)
            VALUES (?, ?, 'watchlist', NULL, NULL, ?, ?, ?)""",
            (agent_id, ticker, confidence, reasoning, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()

    def get_snapshot(self, agent_id: str, current_prices: dict[str, float]) -> PortfolioSnapshot:
        """Get current portfolio state with live prices."""
        cash = self.get_cash(agent_id)
        open_pos = self.get_open_positions(agent_id)
        closed_pos = self.get_closed_positions(agent_id)

        positions_value = 0
        pos_details = []
        for pos in open_pos:
            current_price = current_prices.get(pos["ticker"], pos["entry_price"])
            value = current_price * pos["quantity"]
            positions_value += value
            pnl_pct = ((current_price - pos["entry_price"]) / pos["entry_price"]) * 100
            pos_details.append({
                "id": pos["id"],
                "ticker": pos["ticker"],
                "entry_price": pos["entry_price"],
                "current_price": current_price,
                "quantity": pos["quantity"],
                "value": value,
                "pnl_pct": pnl_pct,
                "stop_loss": pos["stop_loss_price"],
                "take_profit": pos["take_profit_price"],
            })

        total_value = cash + positions_value
        return_pct = ((total_value - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100

        wins = sum(1 for p in closed_pos if p["exit_price"] and p["exit_price"] > p["entry_price"])
        losses = sum(1 for p in closed_pos if p["exit_price"] and p["exit_price"] <= p["entry_price"])
        total_closed = wins + losses
        win_rate = (wins / total_closed * 100) if total_closed > 0 else 0

        return PortfolioSnapshot(
            agent_id=agent_id,
            cash=cash,
            positions_value=positions_value,
            total_value=total_value,
            return_pct=return_pct,
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            positions=pos_details,
        )
