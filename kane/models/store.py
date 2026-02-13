"""店舗・出店計画に関するデータモデル"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class StoreType(Enum):
    DIRECT = "直営店"
    FRANCHISE = "FC店"


class StoreStatus(Enum):
    PLANNING = "計画中"
    SITE_SELECTED = "物件確定"
    UNDER_CONSTRUCTION = "工事中"
    READY = "開店準備"
    OPEN = "営業中"
    CLOSED = "閉店"


class Region(Enum):
    FUKUOKA_CITY = "福岡市"
    KITAKYUSHU = "北九州市"
    KURUME = "久留米市"
    IIZUKA = "飯塚市"
    OMUTA = "大牟田市"
    CHIKUSHINO = "筑紫野市"
    KASUGA = "春日市"
    ONOJO = "大野城市"
    MUNAKATA = "宗像市"
    DAZAIFU = "太宰府市"
    SAGA = "佐賀市"
    NAGASAKI = "長崎市"
    KUMAMOTO = "熊本市"
    OITA = "大分市"
    MIYAZAKI = "宮崎市"
    KAGOSHIMA = "鹿児島市"


@dataclass
class StoreLocation:
    """店舗候補地情報"""
    region: Region
    address: str
    floor_area_sqm: float
    rent_monthly_yen: int
    deposit_yen: int
    key_money_yen: int
    distance_to_station_m: Optional[int] = None
    parking_spaces: int = 0
    nearby_competitors: int = 0
    population_in_3km: int = 0
    construction_industry_density: float = 0.0  # 建設業者密度（3km圏内）


@dataclass
class StoreFinancials:
    """店舗の財務データ"""
    initial_investment_yen: int = 0
    monthly_rent_yen: int = 0
    monthly_personnel_cost_yen: int = 0
    monthly_inventory_cost_yen: int = 0
    monthly_utilities_yen: int = 0
    monthly_other_costs_yen: int = 0
    projected_monthly_revenue_yen: int = 0
    breakeven_months: int = 0

    @property
    def monthly_total_cost(self) -> int:
        return (
            self.monthly_rent_yen
            + self.monthly_personnel_cost_yen
            + self.monthly_inventory_cost_yen
            + self.monthly_utilities_yen
            + self.monthly_other_costs_yen
        )

    @property
    def monthly_profit(self) -> int:
        return self.projected_monthly_revenue_yen - self.monthly_total_cost


@dataclass
class StorePlan:
    """出店計画"""
    store_id: str
    store_name: str
    store_type: StoreType
    status: StoreStatus
    planned_open_year: int
    planned_open_quarter: int  # 1-4
    location: Optional[StoreLocation] = None
    financials: Optional[StoreFinancials] = None
    staff_required: int = 0
    notes: str = ""


@dataclass
class FranchisePlan:
    """FC出店計画"""
    store_plan: StorePlan
    franchisee_name: str = ""
    franchise_fee_yen: int = 3_000_000
    royalty_rate: float = 0.05  # 売上の5%
    contract_years: int = 5
    training_weeks: int = 4
    support_level: str = "標準"


@dataclass
class AnnualExpansionPlan:
    """年間出店計画"""
    year: int
    direct_stores: list[StorePlan] = field(default_factory=list)
    franchise_stores: list[FranchisePlan] = field(default_factory=list)

    @property
    def total_new_stores(self) -> int:
        return len(self.direct_stores) + len(self.franchise_stores)

    @property
    def total_investment(self) -> int:
        direct = sum(
            s.financials.initial_investment_yen
            for s in self.direct_stores
            if s.financials
        )
        fc = sum(
            s.store_plan.financials.initial_investment_yen
            for s in self.franchise_stores
            if s.store_plan.financials
        )
        return direct + fc
