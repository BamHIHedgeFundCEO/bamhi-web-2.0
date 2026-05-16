"""
config/sectors.py
板塊追蹤清單與龍頭股設定 (全站共用，集中管理)
"""

# ==========================================
# 📁 CEO 專屬：寫死在程式裡的追蹤板塊清單
# 只要在這裡新增 "板塊名稱": ["代碼1", "代碼2"...]，網頁選單就會自動擴充！
# ==========================================
TRACKED_SECTORS = {
    "太空概念股 (Space)": ["RKLB", "PL", "LUNR", "ASTS", "RDW","SATS", "VSAT", "FLY", "MDA", "IRDM","YSS","VOYG","SPIR","BKSY","SPCE","TSAT"],
    "存儲記憶體 (Storage)": ["MU", "WDC", "STX", "NTAP","SNDK","RMBS","SIMO"],
    "散熱與液冷 (Cooling)": ["MOD", "NVT"],
    "AI 應用軟體 (AI Apps)": ["ADBE", "ADP", "AI", "APP", "APPS", "ASAN", "BRZE", "CLBT", "CRM", "CVLT", "DDOG", "DOCS", "DOCU", "DUOL", "ESTC", "FIG", "FSLY", "GTLB", "GWRE", "HUBS", "INTU", "IOT", "KVYO", "LIF", "MDB", "MNDY", "NET", "NOW", "PATH", "PCOR", "PINS", "PLTR", "RBLX", "RBRK", "RDDT", "SAP", "SHOP", "SNAP", "SNOW", "SOUN", "SPOT", "TEAM", "TEM", "TTD", "TWLO", "U", "VEEV", "ZETA", "ZM"],
    "稀土與戰略金屬 (Rare Earths)": ["MP", "UUUU", "AREC", "CRML", "NB", "TMC", "IDR", "PPTA", "CLF", "UAMY", "USAR"],
    "光通訊 (Optical Communication)": ["GLW", "LITE", "COHR", "FN", "AAOI", "POET", "MRVL", "CRDO", "ALAB", "ANET", "AVGO", "CIEN", "VIAV", "CLFD", "NOK", "LUMN", "APH"],
    "鈾礦 (Uranium)": ["CCJ", "UEC", "UUUU", "LEU", "ISOU", "UROY", "NXE", "URG", "DNN", "EU", "AEC", "NUCL", "JAGU"],
    "核電與核能技術 (Nuclear Power)": ["OKLO", "UEC", "UUUU", "SMR", "LEU", "CCJ", "NXE", "TLN", "ETN", "CEG", "GHM", "NNE", "KEP", "BWXT", "NEE", "SO", "D", "EMR", "ETR", "VST", "PEG", "DUK", "RWEOY", "XE", "HON", "GEV", "EXC", "PPL"],
    "純血量子計算 (Pure Quantum)": ["IONQ", "RGTI", "QBTS", "QUBT", "ARQQ", "ZPTA", "LAES", "HOLO", "QMCO", "WIMI"],
    "算力租借平台 (AI Compute Infra)": ["NBIS","CRWV", "APLD", "CORZ", "IREN", "WULF", "BTDR", "HUT","HIVE","CIFR","RIOT","CLSK","MARA","GLXY"],
    "微電網與獨立能源島(Microgrids & Energy Islands)": ["BE", "PSIX", "BKR", "STEM", "FIP", "ENPH", "BW","SEI","PLUG","FCEL","BLDP","GNRC"],
    "天然氣供應鏈 (Natural Gas & LNG)": ["LNG", "CQP", "WMB", "KMI", "DTM", "TRGP", "ENB", "TRP", "ET", "OKE", "EPD", "MPLX", "GLNG", "EE", "FLNG", "NFE", "DLNG", "WES", "PBA", "AM", "KNTK", "SMC", "BWLP", "LPG", "NVGS", "NGL"],
    "電力公用事業 (Electric Utilities)": ["CEG", "VST", "TLN", "NEE", "SO", "DUK", "EXC", "PEG", "PPL", "D", "ETR", "NRG", "RWEOY", "KEP", "TAC", "KEN", "DGXX", "DYNC"],
    "電網工程設備 (Grid Infrastructure)": ["PWR", "MYRG", "ETN", "HUBB", "APH", "TEL", "GEV", "DY", "TTEK", "AMRC"],
    "AI 伺服器與硬體 (AI Computing Hardware)": ["SMCI", "DELL","HPE", "LNVGY", "HPQ","OSS","AVGO"], 
    "資料中心基建(Data_Center_Infra)": ["FIX","EME","VRT","IESC","MTZ","ECG","PRIM","AGX","LGN","APG","STRL","J","ACM","CAT","BNC","TEX","MTW"],
    "加密貨幣(Crypto)": ["MSTR", "COIN", "GLXY", "HOOD", "CRCL", "BKKT", "CNCK", "EXOD", "BTCS", "MARA", "RIOT", "CLSK", "IREN", "HUT", "CIFR", "WULF", "BTBT", "ARBK", "BTDR", "CORZ", "APLD", "CAN", "NA", "NCTY", "BGIN", "ICG", "GPUS", "ABTC"]
}

# ==========================================
# 👑 CEO 專屬：每個板塊的龍頭股標記
# 只要在這裡新增或修改，VCP 列表會自動打上 ⭐ 龍頭標記
# ==========================================
SECTOR_LEADERS = {
    "太空概念股 (Space)": ["RKLB", "ASTS", "PL"],
    "存儲記憶體 (Storage)": ["MU", "SNDK", "STX"],
    "散熱與液冷 (Cooling)": ["VRT"],
    "AI 應用軟體 (AI Apps)": ["PLTR", "APP", "NET", "SNOW", "NOW"],
    "稀土與戰略金屬 (Rare Earths)": ["MP", "UUUU", "UAMY", "USAR"],
    "光通訊 (Optical Communication)": ["LITE", "COHR", "GLW"],
    "鈾礦 (Uranium)": ["CCJ", "LEU", "UUUU"],
    "核電與核能技術 (Nuclear Power)": ["CEG", "VST", "ETN"],
    "純血量子計算 (Pure Quantum)": ["IONQ", "RGTI", "QBTS"],
    "算力租借平台 (AI Compute Infra)": ["NBIS", "CRWV", "APLD", "IREN"],
    "微電網與獨立能源島(Microgrids & Energy Islands)": ["BE"],
    "天然氣供應鏈 (Natural Gas & LNG)": ["LNG", "KMI", "WMB", "DTM", "EPD"],
    "電力公用事業 (Electric Utilities)": ["CEG", "VST", "TLN", "NEE"],
    "電網工程設備 (Grid Infrastructure)": ["PWR", "MYRG", "ETN"],
    "AI 伺服器與硬體 (AI Computing Hardware)": ["SMCI", "DELL","HPE","OSS","AVGO"],
    "資料中心基建(Data_Center_Infra)": ["FIX","VRT","MTZ","CAT"],
    "加密貨幣(Crypto)": ["MSTR", "COIN", "HOOD", "CRCL"]
}
