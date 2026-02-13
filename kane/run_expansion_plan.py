"""
ライフクリエイト社 出店拡大計画 - 5エージェント統合実行
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

全5エージェントを実行し、統合レポートを生成する。
"""

import json
from kane.agents.market_analysis import MarketAnalysisAgent
from kane.agents.financial_planning import FinancialPlanningAgent
from kane.agents.location_scout import LocationScoutAgent
from kane.agents.hr_recruitment import HRRecruitmentAgent
from kane.agents.franchise_management import FranchiseManagementAgent


def run_all_agents() -> dict:
    """全エージェントを実行し統合結果を返す"""
    params = {
        "years": 5,
        "existing_direct": 3,
        "existing_fc": 0,
        "starting_cash": 50_000_000,
    }

    print("=" * 60)
    print("  ライフクリエイト社 出店拡大計画 - エージェント統合実行")
    print("=" * 60)

    # Agent 1: 市場分析
    print("\n[1/5] 市場分析エージェント 実行中...")
    market_agent = MarketAnalysisAgent()
    market_result = market_agent.analyze()
    market_plan = market_agent.generate_plan(years=params["years"])
    market_risks = market_agent.identify_risks()
    print(f"  → {market_result.summary}")

    # Agent 2: 財務計画
    print("\n[2/5] 財務計画エージェント 実行中...")
    finance_agent = FinancialPlanningAgent()
    finance_result = finance_agent.analyze(**params)
    finance_plan = finance_agent.generate_plan(**params)
    print(f"  → {finance_result.summary}")

    # Agent 3: 物件探索
    print("\n[3/5] 物件探索エージェント 実行中...")
    location_agent = LocationScoutAgent()
    location_result = location_agent.analyze(years=params["years"])
    location_plan = location_agent.generate_plan(years=params["years"])
    print(f"  → {location_result.summary}")

    # Agent 4: 人材採用
    print("\n[4/5] 人材採用・育成エージェント 実行中...")
    hr_agent = HRRecruitmentAgent()
    hr_result = hr_agent.analyze(**params)
    hr_plan = hr_agent.generate_plan(**params)
    print(f"  → {hr_result.summary}")

    # Agent 5: FC管理
    print("\n[5/5] FC管理エージェント 実行中...")
    fc_agent = FranchiseManagementAgent()
    fc_result = fc_agent.analyze(years=params["years"])
    fc_plan = fc_agent.generate_plan(years=params["years"])
    print(f"  → {fc_result.summary}")

    # 統合レポート
    print("\n" + "=" * 60)
    print("  統合レポート生成中...")
    print("=" * 60)

    report = {
        "計画名": "ライフクリエイト社 5ヵ年出店拡大計画",
        "計画期間": "2026年〜2030年",
        "目標": f"年間{params['years']}店舗（直営5+FC6）× 5年 = 55店舗新規出店",
        "agents": {
            "市場分析": {
                "summary": market_result.summary,
                "recommendations": market_result.recommendations,
                "risks": market_risks,
                "annual_plan": market_plan,
            },
            "財務計画": {
                "summary": finance_result.summary,
                "recommendations": finance_result.recommendations,
                "risks": finance_result.risks,
                "key_figures": {
                    "5年間累計投資額": finance_result.data["total_5year_investment"],
                    "最終店舗数": finance_result.data["final_total_stores"],
                },
            },
            "物件探索": {
                "summary": location_result.summary,
                "recommendations": location_result.recommendations,
                "risks": location_result.risks,
                "criteria": location_result.data["property_criteria"],
            },
            "人材採用": {
                "summary": hr_result.summary,
                "recommendations": hr_result.recommendations,
                "risks": hr_result.risks,
                "5year_total_hires": hr_result.data["total_5year_hires"],
            },
            "FC管理": {
                "summary": fc_result.summary,
                "recommendations": fc_result.recommendations,
                "risks": fc_result.risks,
                "total_fc_stores": fc_result.data["total_fc_stores_5year"],
            },
        },
    }

    # コンソール出力
    print("\n■ 市場分析結果:")
    for r in market_result.recommendations:
        print(f"  - {r}")

    print("\n■ 財務計画:")
    for r in finance_result.recommendations:
        print(f"  - {r}")

    print("\n■ 物件計画:")
    for r in location_result.recommendations:
        print(f"  - {r}")

    print("\n■ 人材計画:")
    for r in hr_result.recommendations:
        print(f"  - {r}")

    print("\n■ FC展開計画:")
    for r in fc_result.recommendations:
        print(f"  - {r}")

    # 統合リスク一覧
    all_risks = []
    all_risks.extend(market_risks)
    all_risks.extend(finance_result.risks)
    all_risks.extend(location_result.risks)
    all_risks.extend(hr_result.risks)
    all_risks.extend(fc_result.risks)

    print(f"\n■ 識別されたリスク総数: {len(all_risks)}件")
    for i, risk in enumerate(all_risks, 1):
        print(f"  {i}. {risk}")

    print("\n" + "=" * 60)
    print("  計画策定完了")
    print("=" * 60)

    return report


if __name__ == "__main__":
    report = run_all_agents()
    with open("expansion_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print("\nレポートを expansion_report.json に保存しました。")
