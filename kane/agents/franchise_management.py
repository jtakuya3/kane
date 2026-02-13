"""
Agent 5: FC管理エージェント (FranchiseManagementAgent)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
役割: フランチャイズ展開の戦略策定と加盟店管理体制を構築する
- FC加盟者の募集・選定戦略
- FC契約条件の設計
- 加盟店支援体制の構築
- ロイヤリティモデルの最適化
"""

from dataclasses import dataclass, field
from typing import Any

from kane.agents.base import BaseAgent, AgentResult
from kane.config.constants import (
    ANNUAL_FRANCHISE_STORES,
    FC_FRANCHISE_FEE,
    FC_ROYALTY_RATE,
    FC_CONTRACT_YEARS,
    FC_TRAINING_WEEKS,
    FC_MONTHLY_REVENUE_TARGET,
    FC_STORE_TOTAL_HQ_INVESTMENT,
)


@dataclass
class FranchisePackage:
    """FCパッケージ"""
    package_name: str
    franchise_fee: int
    royalty_rate: float
    initial_investment_franchisee: int  # 加盟者負担の初期投資
    contract_years: int
    territory_protection_km: float  # テリトリー保護半径
    support_items: list[str] = field(default_factory=list)


@dataclass
class FranchiseeProfile:
    """理想的な加盟者プロファイル"""
    category: str
    requirements: list[str] = field(default_factory=list)
    advantages: list[str] = field(default_factory=list)


@dataclass
class FCRecruitmentPlan:
    """FC加盟者募集計画"""
    year: int
    target_franchisees: int
    recruitment_channels: list[str] = field(default_factory=list)
    estimated_inquiries: int = 0
    estimated_applications: int = 0
    estimated_approvals: int = 0
    recruitment_budget: int = 0


class FranchiseManagementAgent(BaseAgent):
    """
    FC管理エージェント

    年間6店舗のFC出店を実現するための
    フランチャイズ戦略全般を策定・管理する。

    主要機能:
    1. FCパッケージの設計
    2. 加盟者募集・選定プロセスの構築
    3. 加盟店支援体制の設計
    4. FC収益モデルの最適化
    """

    # 加盟者募集の歩留まり
    INQUIRY_TO_APPLICATION_RATE = 0.15
    APPLICATION_TO_APPROVAL_RATE = 0.40
    FC_RECRUITMENT_COST_PER_STORE = 2_000_000

    def __init__(self):
        super().__init__(
            name="FC管理エージェント",
            description="フランチャイズ展開の戦略策定と加盟店管理",
        )

    def design_franchise_packages(self) -> list[FranchisePackage]:
        """FCパッケージを設計"""
        return [
            FranchisePackage(
                package_name="スタンダードプラン",
                franchise_fee=FC_FRANCHISE_FEE,
                royalty_rate=FC_ROYALTY_RATE,
                initial_investment_franchisee=25_000_000,
                contract_years=FC_CONTRACT_YEARS,
                territory_protection_km=3.0,
                support_items=[
                    "開業前研修（4週間）",
                    "店舗設計・施工管理支援",
                    "POS・在庫管理システム提供",
                    "初期在庫の仕入支援",
                    "開業後3ヶ月間の集中サポート",
                    "月次SV訪問（月2回）",
                    "商品供給・仕入れルート提供",
                    "販促ツール・チラシの提供",
                ],
            ),
            FranchisePackage(
                package_name="プレミアムプラン",
                franchise_fee=5_000_000,
                royalty_rate=0.06,
                initial_investment_franchisee=20_000_000,
                contract_years=7,
                territory_protection_km=5.0,
                support_items=[
                    "スタンダードプランの全サポート",
                    "本部による物件調達支援",
                    "開業費用の一部負担（内装工事費50%）",
                    "開業後6ヶ月間の集中サポート",
                    "専任SV配置（月4回訪問）",
                    "法人営業の共同開拓",
                    "マーケティング費用の50%負担",
                    "経営コンサルティング（四半期）",
                ],
            ),
        ]

    def define_ideal_franchisee(self) -> list[FranchiseeProfile]:
        """理想的な加盟者像を定義"""
        return [
            FranchiseeProfile(
                category="建設業経験者",
                requirements=[
                    "建設業界での就業経験5年以上",
                    "工具に関する基礎知識",
                    "自己資金1,000万円以上",
                    "経営者としての意欲",
                ],
                advantages=[
                    "工具の知識・顧客ネットワークを保有",
                    "建設業者へのリーチが容易",
                    "商品選定の目利き力がある",
                ],
            ),
            FranchiseeProfile(
                category="小売業経験者",
                requirements=[
                    "小売業での店舗管理経験3年以上",
                    "自己資金1,000万円以上",
                    "人材マネジメント経験",
                ],
                advantages=[
                    "店舗運営スキルを保有",
                    "接客・販売の基礎力がある",
                    "在庫管理・発注の知識がある",
                ],
            ),
            FranchiseeProfile(
                category="脱サラ起業家",
                requirements=[
                    "社会人経験10年以上",
                    "自己資金1,500万円以上",
                    "経営への強い意欲と学習意欲",
                    "地域でのネットワーク",
                ],
                advantages=[
                    "ビジネス全般のスキルを保有",
                    "資金力がある場合が多い",
                    "事業への情熱が高い",
                ],
            ),
        ]

    def create_recruitment_plan(self, year: int, year_index: int) -> FCRecruitmentPlan:
        """年間FC募集計画を作成"""
        target = ANNUAL_FRANCHISE_STORES
        inquiries = int(target / self.APPLICATION_TO_APPROVAL_RATE / self.INQUIRY_TO_APPLICATION_RATE)
        applications = int(inquiries * self.INQUIRY_TO_APPLICATION_RATE)

        return FCRecruitmentPlan(
            year=year,
            target_franchisees=target,
            recruitment_channels=[
                "フランチャイズ展示会（年2回出展）",
                "FC募集ポータルサイト（フランチャイズWEBリポート等）",
                "自社HP・SNSでの募集",
                "既存加盟者からの紹介",
                "事業承継マッチング（後継者不在の工具店）",
                "地方銀行の取引先紹介",
                "商工会議所を通じた募集",
            ],
            estimated_inquiries=inquiries,
            estimated_applications=applications,
            estimated_approvals=target,
            recruitment_budget=self.FC_RECRUITMENT_COST_PER_STORE * target,
        )

    def analyze(self, **kwargs) -> AgentResult:
        """FC展開計画を分析"""
        years = kwargs.get("years", 5)

        packages = self.design_franchise_packages()
        profiles = self.define_ideal_franchisee()
        recruitment_plans: list[dict[str, Any]] = []

        total_fc_stores = 0
        total_royalty_5year = 0

        for i in range(years):
            year = 2026 + i
            plan = self.create_recruitment_plan(year, i)
            total_fc_stores += plan.target_franchisees

            # ロイヤリティ収入予測（累積FC店舗数 × 月商 × ロイヤリティ率 × 12ヶ月）
            cumulative_fc = (i + 1) * ANNUAL_FRANCHISE_STORES
            annual_royalty = int(
                cumulative_fc * FC_MONTHLY_REVENUE_TARGET * FC_ROYALTY_RATE * 12
            )
            total_royalty_5year += annual_royalty

            recruitment_plans.append({
                "year": plan.year,
                "target": plan.target_franchisees,
                "inquiries_needed": plan.estimated_inquiries,
                "applications_expected": plan.estimated_applications,
                "budget": plan.recruitment_budget,
                "cumulative_fc_stores": cumulative_fc,
                "annual_royalty_income": annual_royalty,
                "annual_fc_fee_income": FC_FRANCHISE_FEE * plan.target_franchisees,
            })

        # FC店舗の本部収益モデル
        fc_revenue_model = {
            "加盟金収入（年間）": f"{FC_FRANCHISE_FEE * ANNUAL_FRANCHISE_STORES:,}円",
            "ロイヤリティ収入（5年目年間）": f"{int(total_fc_stores * FC_MONTHLY_REVENUE_TARGET * FC_ROYALTY_RATE * 12):,}円",
            "商品供給マージン（推定）": "仕入額の5-8%",
            "システム利用料": "月額50,000円/店舗",
            "5年間累計ロイヤリティ": f"{total_royalty_5year:,}円",
        }

        result = AgentResult(
            agent_name=self.name,
            success=True,
            data={
                "packages": [
                    {
                        "name": p.package_name,
                        "fee": p.franchise_fee,
                        "royalty": f"{p.royalty_rate*100:.0f}%",
                        "franchisee_investment": p.initial_investment_franchisee,
                        "contract_years": p.contract_years,
                        "territory_km": p.territory_protection_km,
                        "support": p.support_items,
                    }
                    for p in packages
                ],
                "ideal_profiles": [
                    {
                        "category": p.category,
                        "requirements": p.requirements,
                        "advantages": p.advantages,
                    }
                    for p in profiles
                ],
                "recruitment_plans": recruitment_plans,
                "revenue_model": fc_revenue_model,
                "total_fc_stores_5year": total_fc_stores,
            },
            recommendations=[
                f"5年間で{total_fc_stores}店舗のFC出店を計画",
                f"5年間累計ロイヤリティ収入: {total_royalty_5year:,}円",
                "建設業経験者の加盟を最優先で募集",
                "後継者不在の既存工具店のFC転換を積極推進",
                "プレミアムプランで有力加盟者の獲得を加速",
                "加盟者向けの収支シミュレーションツールを整備",
                "加盟店同士の交流会（年2回）でベストプラクティス共有",
            ],
            risks=self.identify_risks(),
            summary=f"5年間で{total_fc_stores}店舗のFC展開計画を策定。"
            f"累計ロイヤリティ収入{total_royalty_5year:,}円を見込む。",
        )
        self.store_result(result)
        return result

    def generate_plan(self, **kwargs) -> dict[str, Any]:
        """FC展開計画を生成"""
        result = self.analyze(**kwargs)
        return {
            "fc_strategy": {
                "packages": result.data["packages"],
                "target_profiles": result.data["ideal_profiles"],
                "recruitment": result.data["recruitment_plans"],
                "revenue_model": result.data["revenue_model"],
            },
            "support_system": {
                "sv_体制": "FC6店舗あたりSV1名配置",
                "訪問頻度": "月2回（スタンダード）/ 月4回（プレミアム）",
                "本部支援": [
                    "商品供給・物流支援",
                    "販促・マーケティング支援",
                    "システム・IT支援",
                    "経営相談窓口（随時）",
                    "店舗改善コンサルティング（四半期）",
                ],
                "品質管理": [
                    "覆面調査（年2回）",
                    "顧客満足度調査（年1回）",
                    "加盟店評価制度（S/A/B/C）",
                    "改善指導プログラム",
                ],
            },
        }

    def identify_risks(self, **kwargs) -> list[str]:
        """FC関連リスクを特定"""
        return [
            "加盟者候補の確保難（年間100件以上の問い合わせが必要）",
            "加盟者の経営能力のばらつきによる品質格差",
            "FC店の売上不振によるロイヤリティ収入減少",
            "加盟者とのトラブル・契約解除リスク",
            "ブランドイメージの毀損リスク（不良FC店の存在）",
            "テリトリー設計の失敗による加盟者間の競合",
            "FC法制度の変更リスク（中小小売商業振興法改正等）",
        ]
