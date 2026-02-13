"""
Agent 2: 財務計画エージェント (FinancialPlanningAgent)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
役割: 出店に関する投資計画・キャッシュフロー計画を策定する
- 店舗別投資額の算出
- 年度別CF計画の策定
- 資金調達計画の立案
- 投資回収シミュレーション
"""

from dataclasses import dataclass
from typing import Any

from kane.agents.base import BaseAgent, AgentResult
from kane.models.cashflow import MonthlyCashFlow, AnnualCashFlow, MultiYearCashFlow
from kane.config.constants import (
    ANNUAL_DIRECT_STORES,
    ANNUAL_FRANCHISE_STORES,
    DIRECT_STORE_TOTAL_INVESTMENT,
    FC_STORE_TOTAL_HQ_INVESTMENT,
    FC_FRANCHISE_FEE,
    FC_ROYALTY_RATE,
    DIRECT_MONTHLY_REVENUE_TARGET,
    FC_MONTHLY_REVENUE_TARGET,
    DIRECT_MONTHLY_RENT,
    DIRECT_MONTHLY_PERSONNEL,
    DIRECT_MONTHLY_INVENTORY,
    DIRECT_MONTHLY_UTILITIES,
    DIRECT_MONTHLY_OTHER,
    BANK_LOAN_INTEREST_RATE,
    LOAN_TERM_YEARS,
)


@dataclass
class InvestmentSummary:
    """年間投資サマリ"""
    year: int
    direct_store_investment: int
    fc_store_investment: int
    hq_expansion_cost: int
    total_investment: int
    funding_equity: int
    funding_debt: int
    fc_fee_income: int


class FinancialPlanningAgent(BaseAgent):
    """
    財務計画エージェント

    年間11店舗（直営5+FC6）出店のための投資計画、
    キャッシュフロー予測、資金調達計画を策定する。

    主要機能:
    1. 年間投資額の算出と資金調達計画
    2. 5年間のキャッシュフロー予測
    3. 店舗別損益分岐点分析
    4. 累積店舗数に基づく本部収益モデル
    """

    # 売上成長率（2年目以降の既存店）
    EXISTING_STORE_GROWTH_RATE = 0.03
    # 新店の初年度売上達成率（目標比）
    NEW_STORE_FIRST_YEAR_RATIO = 0.70
    # 本部管理費増加（1店舗あたり/月）
    HQ_COST_PER_STORE = 200_000

    def __init__(self):
        super().__init__(
            name="財務計画エージェント",
            description="投資計画・キャッシュフロー計画の策定",
        )

    def calculate_annual_investment(self, year: int, year_index: int) -> InvestmentSummary:
        """年間投資額を算出"""
        direct_inv = DIRECT_STORE_TOTAL_INVESTMENT * ANNUAL_DIRECT_STORES
        fc_inv = FC_STORE_TOTAL_HQ_INVESTMENT * ANNUAL_FRANCHISE_STORES
        hq_cost = 10_000_000 if year_index % 2 == 0 else 5_000_000  # 本部拡充費
        total = direct_inv + fc_inv + hq_cost

        # 資金調達構成: 自己資金30% + 借入70%
        equity = int(total * 0.30)
        debt = total - equity

        fc_fee = FC_FRANCHISE_FEE * ANNUAL_FRANCHISE_STORES

        return InvestmentSummary(
            year=year,
            direct_store_investment=direct_inv,
            fc_store_investment=fc_inv,
            hq_expansion_cost=hq_cost,
            total_investment=total,
            funding_equity=equity,
            funding_debt=debt,
            fc_fee_income=fc_fee,
        )

    def build_annual_cashflow(
        self, year: int, year_index: int, cumulative_direct: int, cumulative_fc: int
    ) -> AnnualCashFlow:
        """年間キャッシュフローを構築"""
        annual = AnnualCashFlow(year=year)

        for month in range(1, 13):
            # 新店は四半期ごとに開店と仮定
            new_direct_this_month = 0
            new_fc_this_month = 0
            if month in (1, 4, 7, 10):
                new_direct_this_month = 1
                new_fc_this_month = 1
            if month == 10:
                new_direct_this_month = 2
                new_fc_this_month = 3

            # 既存店売上（前年からの累積）
            existing_direct_rev = int(
                cumulative_direct
                * DIRECT_MONTHLY_REVENUE_TARGET
                * (1 + self.EXISTING_STORE_GROWTH_RATE) ** year_index
            )
            # 新店売上（初年度は70%稼働）
            new_direct_rev = int(
                new_direct_this_month
                * DIRECT_MONTHLY_REVENUE_TARGET
                * self.NEW_STORE_FIRST_YEAR_RATIO
            )

            total_revenue = existing_direct_rev + new_direct_rev

            # FC ロイヤリティ収入
            fc_royalty = int(
                (cumulative_fc + new_fc_this_month)
                * FC_MONTHLY_REVENUE_TARGET
                * FC_ROYALTY_RATE
            )

            # FC加盟金（新規FC開店月のみ）
            fc_fee = FC_FRANCHISE_FEE * new_fc_this_month

            # コスト
            total_direct_stores = cumulative_direct + new_direct_this_month
            cogs = int(total_revenue * 0.55)  # 原価率55%
            personnel = DIRECT_MONTHLY_PERSONNEL * total_direct_stores
            rent = DIRECT_MONTHLY_RENT * total_direct_stores
            utilities = DIRECT_MONTHLY_UTILITIES * total_direct_stores
            other = (
                DIRECT_MONTHLY_OTHER * total_direct_stores
                + self.HQ_COST_PER_STORE
                * (cumulative_direct + cumulative_fc + new_direct_this_month + new_fc_this_month)
            )

            # 投資CF（新店開店月のみ）
            construction = DIRECT_STORE_TOTAL_INVESTMENT * new_direct_this_month
            fc_support = FC_STORE_TOTAL_HQ_INVESTMENT * new_fc_this_month

            # 財務CF
            new_borrowing = int(
                (construction + fc_support) * 0.70
            ) if (construction + fc_support) > 0 else 0
            # 累積借入の月次返済
            total_cumulative_debt = int(
                (DIRECT_STORE_TOTAL_INVESTMENT * cumulative_direct * 0.70
                 + FC_STORE_TOTAL_HQ_INVESTMENT * cumulative_fc * 0.70)
            )
            monthly_repayment = int(
                total_cumulative_debt / (LOAN_TERM_YEARS * 12)
            ) if total_cumulative_debt > 0 else 0
            interest = int(
                total_cumulative_debt * BANK_LOAN_INTEREST_RATE / 12
            )

            mcf = MonthlyCashFlow(
                year=year,
                month=month,
                revenue=total_revenue,
                cost_of_goods=cogs,
                personnel_cost=personnel,
                rent=rent,
                utilities=utilities,
                franchise_royalty_income=fc_royalty,
                franchise_fee_income=fc_fee,
                other_operating_expense=other,
                store_construction=construction,
                equipment_purchase=fc_support,
                borrowing=new_borrowing,
                repayment=monthly_repayment,
                interest_payment=interest,
            )
            annual.monthly_flows.append(mcf)

        return annual

    def analyze(self, **kwargs) -> AgentResult:
        """5年間の財務分析を実行"""
        years = kwargs.get("years", 5)
        starting_cash = kwargs.get("starting_cash", 50_000_000)
        existing_direct = kwargs.get("existing_direct", 3)  # 既存直営店数
        existing_fc = kwargs.get("existing_fc", 0)  # 既存FC店数

        multi_year = MultiYearCashFlow(starting_cash_balance=starting_cash)
        investments: list[dict[str, Any]] = []

        cumulative_direct = existing_direct
        cumulative_fc = existing_fc

        for i in range(years):
            year = 2026 + i

            inv = self.calculate_annual_investment(year, i)
            investments.append({
                "year": inv.year,
                "direct_investment": inv.direct_store_investment,
                "fc_investment": inv.fc_store_investment,
                "hq_cost": inv.hq_expansion_cost,
                "total_investment": inv.total_investment,
                "equity_needed": inv.funding_equity,
                "debt_needed": inv.funding_debt,
                "fc_fee_income": inv.fc_fee_income,
            })

            annual_cf = self.build_annual_cashflow(
                year, i, cumulative_direct, cumulative_fc
            )
            multi_year.annual_flows.append(annual_cf)

            cumulative_direct += ANNUAL_DIRECT_STORES
            cumulative_fc += ANNUAL_FRANCHISE_STORES

        # サマリデータ
        cf_summary = []
        for af in multi_year.annual_flows:
            cf_summary.append({
                "year": af.year,
                "operating_cf": af.total_operating_cf,
                "investing_cf": af.total_investing_cf,
                "financing_cf": af.total_financing_cf,
                "net_cf": af.total_net_cf,
                "cumulative_balance": multi_year.cumulative_balance(af.year),
            })

        result = AgentResult(
            agent_name=self.name,
            success=True,
            data={
                "investments": investments,
                "cashflow_summary": cf_summary,
                "total_5year_investment": sum(i["total_investment"] for i in investments),
                "final_cumulative_direct": cumulative_direct,
                "final_cumulative_fc": cumulative_fc,
                "final_total_stores": cumulative_direct + cumulative_fc,
            },
            recommendations=[
                f"5年間累計投資額: {sum(i['total_investment'] for i in investments):,}円",
                f"必要自己資金: {sum(i['equity_needed'] for i in investments):,}円",
                f"必要借入額: {sum(i['debt_needed'] for i in investments):,}円",
                f"5年後総店舗数: 直営{cumulative_direct}店 + FC{cumulative_fc}店 = {cumulative_direct + cumulative_fc}店",
                "段階的な資金調達により自己資本比率30%以上を維持すること",
                "3年目以降は既存店のCFで新規出店投資の一部をカバー可能",
            ],
            risks=self.identify_risks(),
            summary=f"5年間で{cumulative_direct + cumulative_fc - existing_direct - existing_fc}店舗出店、"
            f"累計投資額{sum(i['total_investment'] for i in investments):,}円の計画を策定。",
        )
        self.store_result(result)
        return result

    def generate_plan(self, **kwargs) -> dict[str, Any]:
        """資金調達計画を生成"""
        result = self.analyze(**kwargs)
        return {
            "investment_plan": result.data["investments"],
            "cashflow_plan": result.data["cashflow_summary"],
            "funding_strategy": {
                "primary": "地方銀行からの長期借入（福岡銀行・西日本シティ銀行）",
                "secondary": "日本政策金融公庫の新事業拡大融資",
                "tertiary": "既存店舗のキャッシュフローからの内部留保",
                "reserve": "私募債・クラウドファンディングの活用検討",
            },
        }

    def identify_risks(self, **kwargs) -> list[str]:
        """財務リスクを特定"""
        return [
            "急速な出店による資金繰りの逼迫（年間投資額3.4億円超）",
            "新店の売上立ち上がり遅延による計画未達リスク",
            "金利上昇時の借入負担増加（金利+1%で年間約1,500万円増）",
            "FC店の売上不振によるロイヤリティ収入減少",
            "在庫管理の複雑化によるキャッシュコンバージョン悪化",
            "不動産市況の変動による出店コスト上昇",
        ]
