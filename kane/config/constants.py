"""ライフクリエイト社 出店計画定数"""

# === 会社情報 ===
COMPANY_NAME = "株式会社ライフクリエイト"
HEADQUARTERS = "福岡県"
BUSINESS_TYPE = "工具販売"

# === 出店目標 ===
ANNUAL_DIRECT_STORES = 5       # 年間直営出店数
ANNUAL_FRANCHISE_STORES = 6    # 年間FC出店数
ANNUAL_TOTAL_STORES = 11       # 年間合計出店数

# === 直営店 標準投資額（円） ===
DIRECT_STORE_CONSTRUCTION = 15_000_000    # 内装工事費
DIRECT_STORE_EQUIPMENT = 8_000_000        # 什器・設備費
DIRECT_STORE_INITIAL_INVENTORY = 20_000_000  # 初期在庫
DIRECT_STORE_DEPOSIT = 3_000_000          # 敷金・保証金
DIRECT_STORE_OTHER_INITIAL = 4_000_000    # その他初期費用
DIRECT_STORE_TOTAL_INVESTMENT = (
    DIRECT_STORE_CONSTRUCTION
    + DIRECT_STORE_EQUIPMENT
    + DIRECT_STORE_INITIAL_INVENTORY
    + DIRECT_STORE_DEPOSIT
    + DIRECT_STORE_OTHER_INITIAL
)  # = 50,000,000円

# === FC店 標準投資額（円）※本部負担分 ===
FC_STORE_SUPPORT_COST = 5_000_000         # FC立上げ支援費
FC_STORE_TRAINING_COST = 1_500_000        # 研修費用
FC_STORE_SYSTEM_COST = 2_000_000          # システム導入費
FC_STORE_INITIAL_INVENTORY_SUPPORT = 5_000_000  # 初期在庫支援
FC_STORE_TOTAL_HQ_INVESTMENT = (
    FC_STORE_SUPPORT_COST
    + FC_STORE_TRAINING_COST
    + FC_STORE_SYSTEM_COST
    + FC_STORE_INITIAL_INVENTORY_SUPPORT
)  # = 13,500,000円

# === FC 収益条件 ===
FC_FRANCHISE_FEE = 3_000_000              # 加盟金
FC_ROYALTY_RATE = 0.05                    # ロイヤリティ率 5%
FC_CONTRACT_YEARS = 5                     # 契約年数
FC_TRAINING_WEEKS = 4                     # 研修期間（週）

# === 直営店 月次運営費（円） ===
DIRECT_MONTHLY_RENT = 500_000             # 賃料
DIRECT_MONTHLY_PERSONNEL = 2_400_000      # 人件費（店長1名+スタッフ3名）
DIRECT_MONTHLY_INVENTORY = 8_000_000      # 仕入原価
DIRECT_MONTHLY_UTILITIES = 150_000        # 水道光熱費
DIRECT_MONTHLY_OTHER = 300_000            # その他経費

# === 売上目標（円） ===
DIRECT_MONTHLY_REVENUE_TARGET = 15_000_000   # 直営月商目標
FC_MONTHLY_REVENUE_TARGET = 12_000_000       # FC月商目標

# === 人員計画 ===
STAFF_PER_DIRECT_STORE = 4                # 直営店1店舗あたり人数
STORE_MANAGER_SALARY = 350_000            # 店長月給
STAFF_SALARY = 250_000                    # スタッフ月給
HQ_STAFF_PER_5_STORES = 2                # 本部スタッフ増員（5店舗あたり）
SV_PER_FC_STORES = 1                      # SV（6FC店舗あたり1名）
SV_SALARY = 400_000                       # SV月給

# === 物件条件 ===
MIN_FLOOR_AREA_SQM = 100                  # 最小店舗面積(㎡)
MAX_FLOOR_AREA_SQM = 300                  # 最大店舗面積(㎡)
IDEAL_FLOOR_AREA_SQM = 165               # 理想店舗面積(㎡)≒50坪
MIN_PARKING_SPACES = 5                    # 最小駐車場台数
MAX_RENT_PER_SQM = 4_000                  # 最大賃料単価（円/㎡）

# === 資金調達 ===
BANK_LOAN_INTEREST_RATE = 0.025           # 銀行借入金利 2.5%
LOAN_TERM_YEARS = 7                       # 借入期間
EQUITY_RATIO_TARGET = 0.30                # 自己資本比率目標

# === 出店対象エリア優先度 ===
EXPANSION_PRIORITY_AREAS = [
    # (地域名, 優先度, 出店タイプ)
    ("福岡市東区", 1, "直営"),
    ("福岡市博多区", 1, "直営"),
    ("福岡市南区", 2, "直営"),
    ("北九州市小倉北区", 2, "直営"),
    ("北九州市八幡西区", 3, "FC"),
    ("久留米市", 3, "FC"),
    ("飯塚市", 4, "FC"),
    ("春日市", 4, "FC"),
    ("筑紫野市", 4, "FC"),
    ("大野城市", 5, "FC"),
    ("宗像市", 5, "FC"),
    ("佐賀市", 6, "FC"),
    ("長崎市", 7, "FC"),
    ("熊本市", 7, "直営"),
    ("大分市", 8, "FC"),
    ("宮崎市", 9, "FC"),
    ("鹿児島市", 9, "FC"),
]
