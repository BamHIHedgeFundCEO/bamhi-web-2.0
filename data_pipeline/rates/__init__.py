from . import treasury
from . import gdp_fedfunds_rstar

def update():
    print("🔹 [Rates Dept] 開始更新...")
    treasury.update()
    gdp_fedfunds_rstar.update()