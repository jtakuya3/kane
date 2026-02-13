"""
Kane - ライフクリエイト社 出店拡大計画エージェントシステム
福岡県を拠点とする工具販売会社の年間5直営店+6FC店の出店計画を支援する
5つのAIエージェントによる統合計画システム
"""

__version__ = "0.1.0"

from kane.agents.market_analysis import MarketAnalysisAgent
from kane.agents.financial_planning import FinancialPlanningAgent
from kane.agents.location_scout import LocationScoutAgent
from kane.agents.hr_recruitment import HRRecruitmentAgent
from kane.agents.franchise_management import FranchiseManagementAgent

__all__ = [
    "MarketAnalysisAgent",
    "FinancialPlanningAgent",
    "LocationScoutAgent",
    "HRRecruitmentAgent",
    "FranchiseManagementAgent",
]
