"""キャッシュフロー計算モデル"""

from dataclasses import dataclass, field


@dataclass
class MonthlyCashFlow:
    """月次キャッシュフロー"""
    year: int
    month: int
    # 営業CF
    revenue: int = 0
    cost_of_goods: int = 0
    personnel_cost: int = 0
    rent: int = 0
    utilities: int = 0
    franchise_royalty_income: int = 0
    franchise_fee_income: int = 0
    other_operating_income: int = 0
    other_operating_expense: int = 0

    # 投資CF
    store_construction: int = 0
    equipment_purchase: int = 0
    deposit_payment: int = 0
    other_investment: int = 0

    # 財務CF
    borrowing: int = 0
    repayment: int = 0
    interest_payment: int = 0

    @property
    def operating_cash_flow(self) -> int:
        income = (
            self.revenue
            + self.franchise_royalty_income
            + self.franchise_fee_income
            + self.other_operating_income
        )
        expense = (
            self.cost_of_goods
            + self.personnel_cost
            + self.rent
            + self.utilities
            + self.other_operating_expense
        )
        return income - expense

    @property
    def investing_cash_flow(self) -> int:
        return -(
            self.store_construction
            + self.equipment_purchase
            + self.deposit_payment
            + self.other_investment
        )

    @property
    def financing_cash_flow(self) -> int:
        return self.borrowing - self.repayment - self.interest_payment

    @property
    def net_cash_flow(self) -> int:
        return (
            self.operating_cash_flow
            + self.investing_cash_flow
            + self.financing_cash_flow
        )


@dataclass
class AnnualCashFlow:
    """年次キャッシュフローサマリ"""
    year: int
    monthly_flows: list[MonthlyCashFlow] = field(default_factory=list)

    @property
    def total_operating_cf(self) -> int:
        return sum(m.operating_cash_flow for m in self.monthly_flows)

    @property
    def total_investing_cf(self) -> int:
        return sum(m.investing_cash_flow for m in self.monthly_flows)

    @property
    def total_financing_cf(self) -> int:
        return sum(m.financing_cash_flow for m in self.monthly_flows)

    @property
    def total_net_cf(self) -> int:
        return sum(m.net_cash_flow for m in self.monthly_flows)


@dataclass
class MultiYearCashFlow:
    """複数年キャッシュフロー計画"""
    annual_flows: list[AnnualCashFlow] = field(default_factory=list)
    starting_cash_balance: int = 0

    def cumulative_balance(self, year: int) -> int:
        balance = self.starting_cash_balance
        for af in self.annual_flows:
            if af.year <= year:
                balance += af.total_net_cf
        return balance
