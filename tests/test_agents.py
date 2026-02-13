"""5エージェントの基本テスト"""

from kane.agents.market_analysis import MarketAnalysisAgent
from kane.agents.financial_planning import FinancialPlanningAgent
from kane.agents.location_scout import LocationScoutAgent
from kane.agents.hr_recruitment import HRRecruitmentAgent
from kane.agents.franchise_management import FranchiseManagementAgent


def test_market_analysis_agent():
    agent = MarketAnalysisAgent()
    result = agent.analyze()
    assert result.success
    assert len(result.data["area_scores"]) > 0
    assert len(result.recommendations) > 0

    plan = agent.generate_plan(years=3)
    assert "2026" in plan
    assert "直営" in plan["2026"]
    assert "FC" in plan["2026"]

    risks = agent.identify_risks()
    assert len(risks) > 0


def test_financial_planning_agent():
    agent = FinancialPlanningAgent()
    result = agent.analyze(years=5, existing_direct=3, existing_fc=0, starting_cash=50_000_000)
    assert result.success
    assert result.data["total_5year_investment"] > 0
    assert result.data["final_total_stores"] == 3 + 25 + 30  # 既存3 + 直営25 + FC30

    plan = agent.generate_plan(years=5, existing_direct=3, existing_fc=0, starting_cash=50_000_000)
    assert "investment_plan" in plan
    assert "funding_strategy" in plan


def test_location_scout_agent():
    agent = LocationScoutAgent()
    result = agent.analyze(years=5)
    assert result.success
    assert len(result.data["pipeline"]) == 5

    evaluation = agent.evaluate_property(
        property_id="P001",
        area_name="福岡市東区",
        address="福岡市東区箱崎1-1-1",
        area_sqm=165,
        monthly_rent=500_000,
        parking_spaces=8,
        distance_to_main_road_m=50,
        is_ground_floor=True,
        nearby_competitors=1,
        population_3km=150_000,
    )
    assert evaluation.total_score > 0
    assert "◎" in evaluation.recommendation or "○" in evaluation.recommendation


def test_hr_recruitment_agent():
    agent = HRRecruitmentAgent()
    result = agent.analyze(years=5, existing_direct=3, existing_fc=0)
    assert result.success
    assert result.data["total_5year_hires"] > 0
    assert len(result.data["training_programs"]) == 4
    assert len(result.data["recruitment_channels"]) > 0


def test_franchise_management_agent():
    agent = FranchiseManagementAgent()
    result = agent.analyze(years=5)
    assert result.success
    assert result.data["total_fc_stores_5year"] == 30  # 6 × 5年

    plan = agent.generate_plan(years=5)
    assert "fc_strategy" in plan
    assert "support_system" in plan


def test_all_agents_integration():
    """全エージェント統合テスト"""
    agents = [
        MarketAnalysisAgent(),
        FinancialPlanningAgent(),
        LocationScoutAgent(),
        HRRecruitmentAgent(),
        FranchiseManagementAgent(),
    ]
    assert len(agents) == 5

    for agent in agents:
        risks = agent.identify_risks()
        assert isinstance(risks, list)
        assert len(risks) > 0
