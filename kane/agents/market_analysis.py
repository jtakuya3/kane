"""
Agent 1: 市場分析エージェント (MarketAnalysisAgent)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
役割: 出店候補エリアの市場環境を分析し、出店優先度を算出する
- 人口動態・世帯数分析
- 建設業・製造業の事業所密度分析
- 競合店舗の分布と市場シェア推計
- 商圏ポテンシャルスコアリング
"""

from dataclasses import dataclass, field
from typing import Any

from kane.agents.base import BaseAgent, AgentResult
from kane.config.constants import EXPANSION_PRIORITY_AREAS


@dataclass
class MarketData:
    """市場データ"""
    area_name: str
    population: int = 0
    households: int = 0
    construction_companies: int = 0
    manufacturing_companies: int = 0
    competitor_stores: int = 0
    avg_income_yen: int = 0
    growth_rate: float = 0.0  # 人口増減率


@dataclass
class AreaScore:
    """エリアスコアリング結果"""
    area_name: str
    market_size_score: float = 0.0       # 市場規模 (0-100)
    competition_score: float = 0.0       # 競合環境 (0-100, 高い=競合少)
    growth_potential_score: float = 0.0  # 成長性 (0-100)
    accessibility_score: float = 0.0     # アクセス性 (0-100)
    total_score: float = 0.0
    recommended_store_type: str = ""     # "直営" or "FC"
    priority_rank: int = 0


class MarketAnalysisAgent(BaseAgent):
    """
    市場分析エージェント

    出店候補エリアの市場環境を多角的に分析し、
    エリアごとの出店優先度スコアを算出する。

    分析軸:
    1. 市場規模: 人口・世帯数・事業所数から潜在需要を推計
    2. 競合環境: 既存競合の分布と市場飽和度を評価
    3. 成長性: 人口動態・開発計画から将来性を判断
    4. アクセス性: 本部からの距離・物流効率を考慮
    """

    # スコアリングの重み付け
    WEIGHT_MARKET_SIZE = 0.35
    WEIGHT_COMPETITION = 0.25
    WEIGHT_GROWTH = 0.25
    WEIGHT_ACCESSIBILITY = 0.15

    def __init__(self):
        super().__init__(
            name="市場分析エージェント",
            description="出店候補エリアの市場分析とスコアリング",
        )
        self._market_data: list[MarketData] = []
        self._area_scores: list[AreaScore] = []

    def load_market_data(self, data: list[MarketData]) -> None:
        """市場データを読み込む"""
        self._market_data = data

    def _score_market_size(self, data: MarketData) -> float:
        """市場規模スコアを算出（人口+事業所数ベース）"""
        pop_score = min(data.population / 5000, 100)
        biz_score = min(
            (data.construction_companies + data.manufacturing_companies) / 50, 100
        )
        return pop_score * 0.4 + biz_score * 0.6

    def _score_competition(self, data: MarketData) -> float:
        """競合環境スコアを算出（競合が少ないほど高い）"""
        if data.competitor_stores == 0:
            return 90.0
        ratio = data.population / (data.competitor_stores * 10000)
        return min(ratio * 20, 100)

    def _score_growth(self, data: MarketData) -> float:
        """成長性スコアを算出"""
        base = 50.0
        growth_impact = data.growth_rate * 500
        return max(0, min(base + growth_impact, 100))

    def _score_accessibility(self, area_name: str) -> float:
        """アクセス性スコアを算出（福岡本部からの距離ベース）"""
        # 福岡市内が最もアクセスしやすい
        accessibility_map = {
            "福岡市": 95, "春日市": 90, "大野城市": 90,
            "筑紫野市": 85, "太宰府市": 85, "宗像市": 75,
            "久留米市": 70, "飯塚市": 65, "北九州市": 60,
            "大牟田市": 55, "佐賀市": 50, "大分市": 40,
            "長崎市": 35, "熊本市": 35, "宮崎市": 25,
            "鹿児島市": 20,
        }
        for key, score in accessibility_map.items():
            if key in area_name:
                return float(score)
        return 30.0

    def score_area(self, data: MarketData) -> AreaScore:
        """エリアを総合スコアリングする"""
        ms = self._score_market_size(data)
        cs = self._score_competition(data)
        gs = self._score_growth(data)
        ac = self._score_accessibility(data.area_name)

        total = (
            ms * self.WEIGHT_MARKET_SIZE
            + cs * self.WEIGHT_COMPETITION
            + gs * self.WEIGHT_GROWTH
            + ac * self.WEIGHT_ACCESSIBILITY
        )

        # スコアが高い都市部は直営、それ以外はFC推奨
        store_type = "直営" if total >= 65 else "FC"

        return AreaScore(
            area_name=data.area_name,
            market_size_score=round(ms, 1),
            competition_score=round(cs, 1),
            growth_potential_score=round(gs, 1),
            accessibility_score=round(ac, 1),
            total_score=round(total, 1),
            recommended_store_type=store_type,
        )

    def analyze(self, **kwargs) -> AgentResult:
        """全エリアの市場分析を実行"""
        if not self._market_data:
            self._market_data = self._generate_default_market_data()

        self._area_scores = []
        for data in self._market_data:
            score = self.score_area(data)
            self._area_scores.append(score)

        # 優先度順にソート
        self._area_scores.sort(key=lambda x: x.total_score, reverse=True)
        for i, score in enumerate(self._area_scores, 1):
            score.priority_rank = i

        recommendations = []
        risks = []

        # 上位5エリアを直営推奨
        top_direct = [s for s in self._area_scores if s.recommended_store_type == "直営"][:5]
        for s in top_direct:
            recommendations.append(
                f"直営出店推奨: {s.area_name} (スコア: {s.total_score})"
            )

        # FC推奨エリア
        top_fc = [s for s in self._area_scores if s.recommended_store_type == "FC"][:6]
        for s in top_fc:
            recommendations.append(
                f"FC出店推奨: {s.area_name} (スコア: {s.total_score})"
            )

        # リスク分析
        high_competition = [
            s for s in self._area_scores if s.competition_score < 40
        ]
        for s in high_competition:
            risks.append(f"{s.area_name}: 競合過多（競合スコア{s.competition_score}）")

        low_growth = [s for s in self._area_scores if s.growth_potential_score < 30]
        for s in low_growth:
            risks.append(f"{s.area_name}: 人口減少リスク（成長スコア{s.growth_potential_score}）")

        result = AgentResult(
            agent_name=self.name,
            success=True,
            data={
                "area_scores": [
                    {
                        "area": s.area_name,
                        "total_score": s.total_score,
                        "market_size": s.market_size_score,
                        "competition": s.competition_score,
                        "growth": s.growth_potential_score,
                        "accessibility": s.accessibility_score,
                        "type": s.recommended_store_type,
                        "rank": s.priority_rank,
                    }
                    for s in self._area_scores
                ],
            },
            recommendations=recommendations,
            risks=risks,
            summary=f"{len(self._area_scores)}エリアを分析完了。"
            f"直営推奨{len(top_direct)}エリア、FC推奨{len(top_fc)}エリア。",
        )
        self.store_result(result)
        return result

    def generate_plan(self, **kwargs) -> dict[str, Any]:
        """年度別出店エリア計画を生成"""
        if not self._area_scores:
            self.analyze()

        years = kwargs.get("years", 5)
        plan: dict[str, Any] = {}

        remaining = list(self._area_scores)
        for year_offset in range(years):
            year = 2026 + year_offset
            year_plan = {"直営": [], "FC": []}

            direct_count = 0
            fc_count = 0
            to_remove = []

            for score in remaining:
                if direct_count >= 5 and fc_count >= 6:
                    break
                if score.recommended_store_type == "直営" and direct_count < 5:
                    year_plan["直営"].append(score.area_name)
                    direct_count += 1
                    to_remove.append(score)
                elif score.recommended_store_type == "FC" and fc_count < 6:
                    year_plan["FC"].append(score.area_name)
                    fc_count += 1
                    to_remove.append(score)

            for item in to_remove:
                remaining.remove(item)

            plan[str(year)] = year_plan

        return plan

    def identify_risks(self, **kwargs) -> list[str]:
        """市場リスクを特定"""
        risks = [
            "九州全体の人口減少トレンド（年率-0.5%）による市場縮小",
            "大手ホームセンター（コメリ、ナフコ）の工具販売強化",
            "ECサイト（MonotaRO、Amazon）との価格競争激化",
            "建設業界の景気変動による需要の波",
            "福岡市外エリアの商圏人口減少加速",
            "原材料高騰による仕入コスト上昇リスク",
        ]
        return risks

    def _generate_default_market_data(self) -> list[MarketData]:
        """デフォルトの市場データを生成"""
        return [
            MarketData("福岡市東区", 320000, 155000, 450, 280, 3, 3800000, 0.005),
            MarketData("福岡市博多区", 250000, 140000, 520, 350, 5, 4200000, 0.008),
            MarketData("福岡市南区", 270000, 125000, 380, 200, 2, 3600000, 0.003),
            MarketData("福岡市西区", 210000, 100000, 300, 180, 2, 3500000, 0.006),
            MarketData("福岡市早良区", 220000, 105000, 280, 160, 1, 3700000, 0.004),
            MarketData("北九州市小倉北区", 180000, 90000, 350, 250, 4, 3200000, -0.003),
            MarketData("北九州市八幡西区", 160000, 75000, 300, 220, 3, 3000000, -0.005),
            MarketData("久留米市", 300000, 130000, 400, 280, 3, 3100000, -0.002),
            MarketData("飯塚市", 125000, 55000, 200, 150, 1, 2800000, -0.008),
            MarketData("春日市", 115000, 50000, 180, 100, 1, 3400000, 0.002),
            MarketData("大野城市", 105000, 45000, 160, 90, 0, 3500000, 0.003),
            MarketData("筑紫野市", 105000, 45000, 170, 95, 1, 3200000, 0.001),
            MarketData("宗像市", 97000, 42000, 140, 80, 0, 3100000, -0.001),
            MarketData("佐賀市", 230000, 100000, 300, 200, 2, 2900000, -0.003),
            MarketData("長崎市", 400000, 185000, 380, 200, 3, 2800000, -0.007),
            MarketData("熊本市", 740000, 330000, 600, 400, 4, 3100000, 0.001),
            MarketData("大分市", 475000, 215000, 400, 250, 3, 3000000, -0.002),
            MarketData("宮崎市", 400000, 180000, 300, 180, 2, 2700000, -0.004),
            MarketData("鹿児島市", 590000, 270000, 450, 280, 3, 2800000, -0.003),
        ]
