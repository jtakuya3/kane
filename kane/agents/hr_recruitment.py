"""
Agent 4: 人材採用・育成エージェント (HRRecruitmentAgent)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
役割: 出店に必要な人材の採用計画・育成プログラムを策定する
- 店舗スタッフの採用計画
- 店長候補の育成プログラム
- 本部人員の拡充計画
- 採用コスト・人件費の最適化
"""

from dataclasses import dataclass, field
from typing import Any

from kane.agents.base import BaseAgent, AgentResult
from kane.config.constants import (
    ANNUAL_DIRECT_STORES,
    ANNUAL_FRANCHISE_STORES,
    STAFF_PER_DIRECT_STORE,
    STORE_MANAGER_SALARY,
    STAFF_SALARY,
    HQ_STAFF_PER_5_STORES,
    SV_PER_FC_STORES,
    SV_SALARY,
)


@dataclass
class StaffingPlan:
    """年間人員計画"""
    year: int
    new_store_managers: int = 0
    new_store_staff: int = 0
    new_sv: int = 0
    new_hq_staff: int = 0
    total_new_hires: int = 0
    estimated_turnover: int = 0  # 離職による補充
    total_recruitment_target: int = 0
    recruitment_cost: int = 0
    annual_personnel_cost_increase: int = 0


@dataclass
class TrainingProgram:
    """研修プログラム"""
    name: str
    target: str
    duration_weeks: int
    content: list[str] = field(default_factory=list)
    cost_per_person: int = 0


@dataclass
class RecruitmentChannel:
    """採用チャネル"""
    channel_name: str
    cost_per_hire: int
    expected_quality: str  # "高", "中", "低"
    lead_time_weeks: int
    volume_capacity: int  # 年間採用可能数


class HRRecruitmentAgent(BaseAgent):
    """
    人材採用・育成エージェント

    年間11店舗出店に必要な人材を計画的に確保・育成する。
    工具販売の専門知識を持つ人材の希少性を考慮し、
    採用戦略と育成プログラムを統合的に設計する。

    主要機能:
    1. 年間採用計画の策定（職種別・チャネル別）
    2. 店長育成パイプラインの構築
    3. FC向けSV(スーパーバイザー)の確保
    4. 採用コスト・人件費の予測
    """

    TURNOVER_RATE = 0.15  # 年間離職率15%
    RECRUITMENT_COST_MANAGER = 800_000    # 店長1名の採用コスト
    RECRUITMENT_COST_STAFF = 300_000      # スタッフ1名の採用コスト
    RECRUITMENT_COST_SV = 1_000_000       # SV1名の採用コスト
    RECRUITMENT_COST_HQ = 500_000         # 本部スタッフ1名の採用コスト
    MANAGER_TRAINING_PERIOD_MONTHS = 6    # 店長育成期間
    STAFF_TRAINING_PERIOD_WEEKS = 4       # スタッフ研修期間

    def __init__(self):
        super().__init__(
            name="人材採用・育成エージェント",
            description="出店に必要な人材の採用計画・育成プログラム策定",
        )

    def calculate_annual_staffing(
        self, year: int, year_index: int, cumulative_direct: int, cumulative_fc: int
    ) -> StaffingPlan:
        """年間人員計画を算出"""
        new_managers = ANNUAL_DIRECT_STORES
        new_staff = ANNUAL_DIRECT_STORES * (STAFF_PER_DIRECT_STORE - 1)  # 店長除く
        new_sv = max(1, ANNUAL_FRANCHISE_STORES // 6)
        new_hq = HQ_STAFF_PER_5_STORES if (year_index + 1) % 1 == 0 else 0

        total_new = new_managers + new_staff + new_sv + new_hq

        # 離職補充
        existing_staff = (
            cumulative_direct * STAFF_PER_DIRECT_STORE
            + cumulative_fc // 6 * SV_PER_FC_STORES  # SV
            + (year_index + 1) * HQ_STAFF_PER_5_STORES  # 本部
        )
        turnover = int(existing_staff * self.TURNOVER_RATE)

        total_target = total_new + turnover

        # 採用コスト
        cost = (
            new_managers * self.RECRUITMENT_COST_MANAGER
            + new_staff * self.RECRUITMENT_COST_STAFF
            + new_sv * self.RECRUITMENT_COST_SV
            + new_hq * self.RECRUITMENT_COST_HQ
            + turnover * self.RECRUITMENT_COST_STAFF
        )

        # 人件費増分（年間）
        personnel_increase = (
            new_managers * STORE_MANAGER_SALARY * 12
            + new_staff * STAFF_SALARY * 12
            + new_sv * SV_SALARY * 12
            + new_hq * STAFF_SALARY * 12
        )

        return StaffingPlan(
            year=2026 + year_index,
            new_store_managers=new_managers,
            new_store_staff=new_staff,
            new_sv=new_sv,
            new_hq_staff=new_hq,
            total_new_hires=total_new,
            estimated_turnover=turnover,
            total_recruitment_target=total_target,
            recruitment_cost=cost,
            annual_personnel_cost_increase=personnel_increase,
        )

    def design_training_programs(self) -> list[TrainingProgram]:
        """研修プログラムを設計"""
        return [
            TrainingProgram(
                name="店長育成プログラム",
                target="店長候補者",
                duration_weeks=24,
                content=[
                    "工具製品知識（電動工具・手工具・測定工具・安全用品）",
                    "店舗運営管理（在庫・発注・棚割り）",
                    "顧客対応・法人営業スキル",
                    "スタッフマネジメント・シフト管理",
                    "売上分析・販促企画",
                    "コンプライアンス・安全管理",
                    "既存店でのOJT（3ヶ月）",
                ],
                cost_per_person=500_000,
            ),
            TrainingProgram(
                name="スタッフ基礎研修",
                target="新規スタッフ",
                duration_weeks=4,
                content=[
                    "工具基礎知識（主要メーカー・製品カテゴリ）",
                    "接客・レジ操作",
                    "在庫管理・検品作業",
                    "安全衛生教育",
                    "POS・在庫管理システム操作",
                ],
                cost_per_person=100_000,
            ),
            TrainingProgram(
                name="SV養成プログラム",
                target="SV候補（FC管理担当）",
                duration_weeks=12,
                content=[
                    "FC契約・運営ルール",
                    "加盟店指導・業績改善手法",
                    "エリアマネジメント",
                    "本部-加盟店間のコミュニケーション",
                    "売上・在庫分析によるコンサルティング",
                    "トラブル対応・クレーム処理",
                ],
                cost_per_person=300_000,
            ),
            TrainingProgram(
                name="FC加盟者研修",
                target="FC加盟オーナー",
                duration_weeks=4,
                content=[
                    "ライフクリエイトの経営理念・ブランド基準",
                    "工具製品知識（基礎〜応用）",
                    "店舗運営マニュアル",
                    "発注・在庫管理システム",
                    "経営管理・収支管理",
                    "既存店での実地研修（2週間）",
                ],
                cost_per_person=0,  # 加盟金に含む
            ),
        ]

    def define_recruitment_channels(self) -> list[RecruitmentChannel]:
        """採用チャネルを定義"""
        return [
            RecruitmentChannel("Indeed/求人ボックス", 50_000, "中", 4, 30),
            RecruitmentChannel("リクナビNEXT/doda", 200_000, "中〜高", 6, 15),
            RecruitmentChannel("ハローワーク", 0, "中", 8, 10),
            RecruitmentChannel("人材紹介（店長・SV）", 800_000, "高", 8, 5),
            RecruitmentChannel("社員紹介制度", 100_000, "高", 4, 10),
            RecruitmentChannel("地元専門学校との連携", 50_000, "中", 12, 8),
            RecruitmentChannel("SNS採用（Instagram/X）", 30_000, "中", 6, 20),
        ]

    def analyze(self, **kwargs) -> AgentResult:
        """5年間の人材計画を分析"""
        years = kwargs.get("years", 5)
        existing_direct = kwargs.get("existing_direct", 3)
        existing_fc = kwargs.get("existing_fc", 0)

        staffing_plans: list[dict[str, Any]] = []
        cumulative_direct = existing_direct
        cumulative_fc = existing_fc
        total_hires = 0
        total_cost = 0

        for i in range(years):
            plan = self.calculate_annual_staffing(
                2026 + i, i, cumulative_direct, cumulative_fc
            )
            staffing_plans.append({
                "year": plan.year,
                "new_managers": plan.new_store_managers,
                "new_staff": plan.new_store_staff,
                "new_sv": plan.new_sv,
                "new_hq": plan.new_hq_staff,
                "turnover_replacement": plan.estimated_turnover,
                "total_target": plan.total_recruitment_target,
                "recruitment_cost": plan.recruitment_cost,
                "personnel_cost_increase": plan.annual_personnel_cost_increase,
            })
            total_hires += plan.total_recruitment_target
            total_cost += plan.recruitment_cost
            cumulative_direct += ANNUAL_DIRECT_STORES
            cumulative_fc += ANNUAL_FRANCHISE_STORES

        programs = self.design_training_programs()
        channels = self.define_recruitment_channels()

        result = AgentResult(
            agent_name=self.name,
            success=True,
            data={
                "staffing_plans": staffing_plans,
                "training_programs": [
                    {
                        "name": p.name,
                        "target": p.target,
                        "duration_weeks": p.duration_weeks,
                        "content": p.content,
                        "cost": p.cost_per_person,
                    }
                    for p in programs
                ],
                "recruitment_channels": [
                    {
                        "channel": c.channel_name,
                        "cost_per_hire": c.cost_per_hire,
                        "quality": c.expected_quality,
                        "lead_time_weeks": c.lead_time_weeks,
                        "capacity": c.volume_capacity,
                    }
                    for c in channels
                ],
                "total_5year_hires": total_hires,
                "total_5year_recruitment_cost": total_cost,
            },
            recommendations=[
                f"5年間で合計{total_hires}名の採用が必要（新規+離職補充）",
                f"累計採用コスト: {total_cost:,}円",
                "店長候補は開店6ヶ月前に確保し育成プログラムを開始すること",
                "建設業界経験者の中途採用を優先（工具知識の即戦力化）",
                "社員紹介制度の充実（紹介報奨金10万円）で質の高い人材を確保",
                "九州地区の工業系専門学校との採用パイプライン構築",
                "離職防止のため福利厚生・キャリアパスの整備が急務",
            ],
            risks=self.identify_risks(),
            summary=f"5年間で{total_hires}名の採用計画を策定。"
            f"採用コスト総額{total_cost:,}円。店長育成パイプラインが最重要課題。",
        )
        self.store_result(result)
        return result

    def generate_plan(self, **kwargs) -> dict[str, Any]:
        """採用・育成計画を生成"""
        result = self.analyze(**kwargs)
        return {
            "staffing_plan": result.data["staffing_plans"],
            "training_plan": result.data["training_programs"],
            "recruitment_strategy": {
                "channels": result.data["recruitment_channels"],
                "priority_actions": [
                    "Q1: 年間採用計画確定・募集媒体選定",
                    "Q2: 上期入社者の研修実施・店長候補OJT開始",
                    "Q3: 下期採用活動本格化・来年度計画着手",
                    "Q4: 来年度店長候補の先行採用・育成開始",
                ],
            },
        }

    def identify_risks(self, **kwargs) -> list[str]:
        """人材関連リスクを特定"""
        return [
            "工具知識を持つ人材の絶対的な不足",
            "九州エリアの労働人口減少による採用難",
            "急速な出店ペースに店長育成が追いつかないリスク",
            "人材の質を維持しながら量を確保する困難さ",
            "離職率上昇リスク（急拡大期の組織不安定化）",
            "人件費高騰（最低賃金上昇+人手不足プレミアム）",
            "FC加盟者の人材確保・教育水準の維持困難",
        ]
