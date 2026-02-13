"""
Agent 3: 物件探索エージェント (LocationScoutAgent)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
役割: 出店候補物件の探索・評価・選定を行う
- 物件条件の定義と候補物件のスクリーニング
- 立地条件スコアリング
- 賃料交渉ポイントの提案
- 物件取得スケジュール管理
"""

from dataclasses import dataclass, field
from typing import Any

from kane.agents.base import BaseAgent, AgentResult
from kane.models.store import StoreLocation, Region
from kane.config.constants import (
    MIN_FLOOR_AREA_SQM,
    MAX_FLOOR_AREA_SQM,
    IDEAL_FLOOR_AREA_SQM,
    MIN_PARKING_SPACES,
    MAX_RENT_PER_SQM,
    ANNUAL_DIRECT_STORES,
    ANNUAL_FRANCHISE_STORES,
)


@dataclass
class PropertyCriteria:
    """物件選定基準"""
    min_area_sqm: float = MIN_FLOOR_AREA_SQM
    max_area_sqm: float = MAX_FLOOR_AREA_SQM
    ideal_area_sqm: float = IDEAL_FLOOR_AREA_SQM
    min_parking: int = MIN_PARKING_SPACES
    max_rent_per_sqm: int = MAX_RENT_PER_SQM
    prefer_ground_floor: bool = True
    prefer_road_facing: bool = True
    min_frontage_m: float = 8.0
    max_distance_to_main_road_m: int = 200


@dataclass
class PropertyEvaluation:
    """物件評価結果"""
    property_id: str
    area_name: str
    address: str
    area_sqm: float
    monthly_rent: int
    location_score: float = 0.0
    cost_score: float = 0.0
    facility_score: float = 0.0
    total_score: float = 0.0
    recommendation: str = ""
    negotiation_points: list[str] = field(default_factory=list)


@dataclass
class PropertyPipeline:
    """物件パイプライン（年間の物件確保計画）"""
    year: int
    target_properties: int = 0
    identified: int = 0
    under_negotiation: int = 0
    contracted: int = 0
    properties: list[PropertyEvaluation] = field(default_factory=list)


class LocationScoutAgent(BaseAgent):
    """
    物件探索エージェント

    工具販売店に最適な物件を探索・評価する。
    ロードサイド型店舗を前提とした立地評価が特徴。

    評価軸:
    1. 立地: 幹線道路沿い、建設現場へのアクセス、商圏人口
    2. コスト: 賃料水準、初期投資額、ランニングコスト
    3. 施設: 面積、駐車場、搬入口、天井高
    """

    WEIGHT_LOCATION = 0.40
    WEIGHT_COST = 0.30
    WEIGHT_FACILITY = 0.30

    def __init__(self):
        super().__init__(
            name="物件探索エージェント",
            description="出店候補物件の探索・評価・選定",
        )
        self._criteria = PropertyCriteria()
        self._pipeline: list[PropertyPipeline] = []

    def evaluate_property(
        self,
        property_id: str,
        area_name: str,
        address: str,
        area_sqm: float,
        monthly_rent: int,
        parking_spaces: int,
        distance_to_main_road_m: int,
        is_ground_floor: bool,
        nearby_competitors: int,
        population_3km: int,
    ) -> PropertyEvaluation:
        """物件を評価する"""
        # 立地スコア
        road_score = max(0, 100 - distance_to_main_road_m * 0.5)
        pop_score = min(population_3km / 3000, 100)
        comp_penalty = nearby_competitors * 15
        location_score = (road_score * 0.4 + pop_score * 0.4) - comp_penalty
        location_score = max(0, min(location_score, 100))
        if is_ground_floor:
            location_score = min(location_score + 10, 100)

        # コストスコア
        rent_per_sqm = monthly_rent / area_sqm if area_sqm > 0 else 99999
        cost_score = max(0, 100 - (rent_per_sqm / self._criteria.max_rent_per_sqm * 100))
        cost_score = max(0, min(cost_score, 100))

        # 施設スコア
        area_diff = abs(area_sqm - self._criteria.ideal_area_sqm)
        area_score = max(0, 100 - area_diff * 0.5)
        parking_score = min(parking_spaces / self._criteria.min_parking * 100, 100)
        facility_score = area_score * 0.5 + parking_score * 0.5

        total = (
            location_score * self.WEIGHT_LOCATION
            + cost_score * self.WEIGHT_COST
            + facility_score * self.WEIGHT_FACILITY
        )

        # 交渉ポイント
        negotiation_points = []
        if rent_per_sqm > self._criteria.max_rent_per_sqm * 0.8:
            negotiation_points.append("賃料の減額交渉（周辺相場との比較を提示）")
        if area_sqm > self._criteria.ideal_area_sqm * 1.2:
            negotiation_points.append("広すぎる場合は一部分割利用の交渉")
        negotiation_points.append("フリーレント期間（内装工事期間中）の確保")
        negotiation_points.append("長期契約（5年以上）による賃料優遇")

        if total >= 70:
            recommendation = "◎ 強く推奨"
        elif total >= 55:
            recommendation = "○ 推奨"
        elif total >= 40:
            recommendation = "△ 条件付き検討"
        else:
            recommendation = "× 見送り"

        return PropertyEvaluation(
            property_id=property_id,
            area_name=area_name,
            address=address,
            area_sqm=area_sqm,
            monthly_rent=monthly_rent,
            location_score=round(location_score, 1),
            cost_score=round(cost_score, 1),
            facility_score=round(facility_score, 1),
            total_score=round(total, 1),
            recommendation=recommendation,
            negotiation_points=negotiation_points,
        )

    def analyze(self, **kwargs) -> AgentResult:
        """物件パイプラインを分析"""
        years = kwargs.get("years", 5)
        self._pipeline = []

        total_target = ANNUAL_DIRECT_STORES + ANNUAL_FRANCHISE_STORES

        for i in range(years):
            year = 2026 + i
            pipeline = PropertyPipeline(year=year, target_properties=total_target)

            # シミュレーション: 年度が進むにつれ物件確保が難しくなる
            pipeline.identified = max(total_target, int(total_target * 1.5) - i * 2)
            pipeline.under_negotiation = total_target + max(0, 3 - i)
            pipeline.contracted = total_target

            self._pipeline.append(pipeline)

        pipeline_data = []
        for p in self._pipeline:
            pipeline_data.append({
                "year": p.year,
                "target": p.target_properties,
                "identified": p.identified,
                "negotiating": p.under_negotiation,
                "contracted": p.contracted,
                "fulfillment_rate": f"{p.contracted / p.target_properties * 100:.0f}%",
            })

        result = AgentResult(
            agent_name=self.name,
            success=True,
            data={
                "pipeline": pipeline_data,
                "property_criteria": {
                    "面積": f"{self._criteria.min_area_sqm}〜{self._criteria.max_area_sqm}㎡（理想: {self._criteria.ideal_area_sqm}㎡）",
                    "駐車場": f"{self._criteria.min_parking}台以上",
                    "最大賃料単価": f"{self._criteria.max_rent_per_sqm:,}円/㎡",
                    "形態": "ロードサイド1階・間口8m以上",
                },
                "sourcing_channels": [
                    "地場不動産仲介会社との連携（三好不動産、エイブル等）",
                    "法人向け不動産データベースの活用",
                    "閉店・撤退店舗情報の早期取得ネットワーク構築",
                    "自治体の産業誘致制度の活用",
                    "居抜き物件の優先確保",
                ],
            },
            recommendations=[
                "年間11件の物件確保にはパイプラインに常時15件以上の候補を維持",
                "不動産仲介業者3社以上と業務委託契約を締結",
                "居抜き物件（元コンビニ・小型量販店）の活用で初期投資を20%削減可能",
                "FC店は加盟者の自己所有物件活用を優先しコスト低減",
                "出店6ヶ月前までに物件確定が必要（工事・許認可期間考慮）",
            ],
            risks=self.identify_risks(),
            summary=f"5年間で{total_target * years}物件の確保計画を策定。"
            "物件パイプラインの継続的な充実が最重要課題。",
        )
        self.store_result(result)
        return result

    def generate_plan(self, **kwargs) -> dict[str, Any]:
        """物件取得スケジュールを生成"""
        years = kwargs.get("years", 5)
        schedule = {}

        for i in range(years):
            year = 2026 + i
            schedule[str(year)] = {
                "Q1": {
                    "action": "候補物件リストアップ・1次評価",
                    "target": "年間候補15件以上特定",
                },
                "Q2": {
                    "action": "物件交渉・契約（上期出店分）",
                    "target": "5件契約完了",
                },
                "Q3": {
                    "action": "下期出店物件の確定・工事着工",
                    "target": "6件契約完了",
                },
                "Q4": {
                    "action": "翌年度候補の先行調査開始",
                    "target": "翌年度候補10件以上特定",
                },
            }

        return schedule

    def identify_risks(self, **kwargs) -> list[str]:
        """物件関連リスクを特定"""
        return [
            "ロードサイド型物件の供給不足（特に福岡市内）",
            "賃料上昇トレンド（福岡市は年率2-3%上昇）",
            "出店スピードに物件確保が追いつかないリスク",
            "居抜き物件の内装改修コストの想定超過",
            "用途地域・建築基準法による出店制限",
            "近隣住民の反対による出店断念リスク",
        ]
