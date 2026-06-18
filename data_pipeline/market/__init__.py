"""
市場部門經理
"""
from . import breadth
from . import strength
from . import naaim
from . import sentiment
from . import world_sectors
from . import market_radar

def update():
    print("🔹 [Market Dept] 開始更新...")
    breadth.update()
    strength.update()
    naaim.update()
    sentiment.update()
    world_sectors.update()
    market_radar.update()