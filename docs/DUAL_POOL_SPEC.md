# BamHI 左側初期 / 右側動能 雙池選股系統 — 完整實作規格書

> 交付對象：Claude Code（實作用）
> 版本：**v1.1** | 定位：自足規格，照此實作即可
> 語言：條件/門檻用中文描述，對外 API 欄位名保留英文
> 本文件只寫「做什麼、條件、規則」，程式碼由實作端撰寫
> 前端頁名：「小市值策略」（掛在交易工具下拉）

---

## v1.1 變更記錄（相對 v1.0）

| # | 變更 | 章節 |
|---|---|---|
| 0 | 市值篩選改為 **$150M–$20B**（左右池同），移除「嚴收 $2B」待決定項。註記：$20B 已含中型股，與「小市值」頁名不符，命名去留由使用者決定 | §4.2, §11 |
| 1 | 補 institution 因子資料管線（13F 反向索引季度 job）— v1.0 整條漏掉 | §6.9 |
| 2 | 回測 universe 改為「上線日起每日快照（forward-test）+ 回溯段明記倖存者偏差」— v1.0 要求含下市股但 yfinance 拉不到，免費層做不到 | §9 |
| 3 | 補 track_record 驗證管線（每週到期檢核 job）— v1.0 只寫入不驗證，guidance_missed veto 永遠不觸發 | §7.6 |
| 4 | 補 L0→L1 量級與批次策略（$20B 後 universe 估 2,500–3,500 檔）| §4.3 |
| 5 | watchpool 加遲滯機制（進池保留 10 交易日）| §5.6 |
| 6 | 明定 Gate 為顯示層過濾，前端兩級呈現（池內觀察 / 過 Gate 候選）| §7.4 |
| 7 | veto 加時間窗（dilution 180 天 / integrity 365 天）| §7.5 |
| 8 | cash_runway 定義：TTM operating CF / 4，缺資料略過並標 data_gap | §7.5 |
| 9 | insider 因子公式：90 日淨買入金額 / 市值，池內 percentile | §7.2 |
| 10 | cron 改 22:00 UTC（06:00 TPE，美股收盤後）— v1.0 的 13:00 UTC 是美東盤前，拉到 T-1 收盤 | §8.1 |
| 11 | 左右互斥靠 §5.6 判定順序保證（entangle=0.06 邊界兩側條件同時成立），非條件本身保證 — 實作註解必寫 | §5.6 |
| 12 | headline 語言定為中文 | §6.3 |
| 13 | 註記：catalyst decay 用抽取時 timeline_months 固定值，不隨時間推進，僅到期懸崖 — 已知簡化 | §7.3 |
| 14 | NIM 備援補 env 變數名 | §2 |

---

## 0. 系統目標與範圍

蓋一條**事件驅動的小市值選股管線**，每日夜間批次執行，產出兩份候選清單：

- **左池（左側初期）**：長期均線低位盤整、剛拐頭、還沒形成趨勢的最早期標的。目標是抓「有機會爆發成領導股」的底部起漲點。報酬最高、勝率最低。定位為**核心倉**。
- **右池（右側動能）**：多頭排列已確認、動能在走的標的。定位為**衛星/動能倉**，快進快出。

系統**不做**下單執行，只產出「評分後的候選清單 + 事件流」，買賣由人工決策。

四層管線：
```
L0 粗篩(yfscreen)→ L1 形態識別(本地算)→ L2 催化劑抽取(EDGAR+LLM)→ L3 評分(左右各一計分卡)
```

**現金成本目標 = $0**，全部用免費層服務。

> [v1.1 註] 市值上限 $20B 已涵蓋中型股，「小市值策略」頁名與實際範圍不完全相符。純命名問題，由使用者決定是否改名。

---

## 1. 架構總圖與資料流

```
每日夜間 GitHub Actions(cron)
│
├─ L0  yfscreen 對 Yahoo screener API 粗篩
│      輸出：粗篩 universe(左右各一批 ticker，可重疊)
│         ↓
├─ L1  對每個 ticker 用 yfinance 拉歷史價/財報，本地算形態
│      判定進「左池 / 右池 / 丟棄」(三選一，左右互斥)
│      輸出：watchpool 表(含 side 欄位)
│         ↓
├─ L2  對兩池 ticker 拉 EDGAR 8-K/PR 增量
│      規則過濾噪音 → LLM 抽取事件為 JSON → 寫 events 表
│         ↓
├─ L3  對每檔算計分卡(左右各一權重表)+ veto 否決
│      輸出：scores 表(每日快照)
│         ↓
└─ 前端(Vercel/Vue)只讀已算好的分數，零運算
```

**鐵律 1：前端絕不觸發 LLM 或即時運算。** 所有重運算在夜間批次完成，前端經 FastAPI backend 只 SELECT。
**鐵律 2：L0 只做 screener 有欄位的事；技術面形態一律落到 L1 自己算。** 兩者不可混。

---

## 2. 零成本技術棧

| 元件 | 服務 | 免費額度 | 用途 |
|---|---|---|---|
| 排程運算 | GitHub Actions | 公開 repo 無限分鐘 | 全部批次 |
| 資料庫 | Supabase 免費層 | 500MB / 50K MAU | 全部表 |
| 前端 | Vercel Hobby | — | 呈現頁 |
| 粗篩 | yfscreen(Yahoo screener API) | 免費，每次 ≤250 筆，自動分頁 | L0 |
| 行情/財報 | yfinance | 免費 | L1 形態計算 |
| 美股申報 | SEC EDGAR API/RSS | 免費，需 User-Agent，≤10 req/s | L2 + §6.9 13F |
| LLM 抽取 | 主：Gemini Flash 免費層 / 備：NVIDIA NIM / 底：規則引擎 | 每日配額遠大於需求 | L2 |

**LLM 三層降級順序：Gemini → NIM → 規則引擎。** 任一層掛掉自動接手，管線永不斷。

**Key 管理**：`GEMINI_API_KEY`、`NVIDIA_NIM_API_KEY` 只放 GitHub Actions secrets 與 `backend/.env`（gitignored）。任何檔案（含本規格書）不得出現 key 本體。建議加 gitleaks pre-commit。

---

## 3. Supabase 資料表 Schema

### 3.1 `watchpool`(L1 輸出)
| 欄位 | 型別 | 說明 |
|---|---|---|
| ticker | TEXT PK | |
| side | TEXT | 'left' \| 'right' |
| market | TEXT | 'US'(台股版為 'TW') |
| market_cap | NUMERIC | |
| entangle | NUMERIC | 長均線糾纏度(L1 算) |
| slope200 | NUMERIC | MA200 斜率 |
| dist_low | NUMERIC | 距 52 週低比例 |
| adv_dollar | NUMERIC | 20 日均成交額 |
| liquidity_ok | BOOLEAN | |
| low_adv_streak | INT | [v1.1 實作補充] 連續 adv_dollar<$2M 交易日數（§5.6 rolling counter，連 5 日→移出） |
| status | TEXT | [v1.1 實作補充] 'active' \| 'cooldown'。移出採軟刪除：標 cooldown 不刪列，供 §5.6 冷卻檢查；讀取端只取 active |
| removed_at | DATE | [v1.1 實作補充] 移出日（status='cooldown' 時有值）；冷卻期滿且未重進由管線清列 |
| entered_at | DATE | [v1.1] 進池日，遲滯機制用(§5.6) |
| updated_at | TIMESTAMPTZ | |

> [v1.1 實作補充] 冷卻持久化選「watchpool 軟刪除」而非獨立 state 表：單一持久化路徑同時覆蓋 Supabase 與本地 JSON fallback，且守住階段 1 只建兩張表。

### 3.2 `events`(L2 輸出)
| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGSERIAL PK | |
| ticker | TEXT | |
| event_date | DATE | 事件發生日 |
| known_at | TIMESTAMPTZ | **系統得知時間(point-in-time 核心)** |
| source | TEXT | '8-K' \| 'PR' \| 'Form4' … |
| source_url | TEXT | |
| event_type | TEXT | 見 §6.4 枚舉 |
| headline | TEXT | 中立一句話 ≤20 字，**中文** |
| counterparty | TEXT | 可 NULL |
| counterparty_tier | TEXT | tier1_giant \| tier2 \| unknown |
| magnitude_usd | NUMERIC | 可 NULL |
| magnitude_pct_rev | NUMERIC | 可 NULL |
| timeline_months | INT | 可 NULL |
| is_recurring | BOOLEAN | |
| specificity | SMALLINT | 1–5 |
| direction | TEXT | bullish \| bearish \| neutral |
| is_integrity_flag | BOOLEAN | |
| is_dilution_flag | BOOLEAN | |
| evidence_anchor | TEXT | ≤15 字錨句，審計用 |
| extraction_method | TEXT | 'llm' \| 'rule' |

### 3.3 `scores`(L3 輸出，每日快照)
| 欄位 | 型別 | 說明 |
|---|---|---|
| ticker | TEXT | |
| score_date | DATE | |
| side | TEXT | |
| total | NUMERIC | 0–100 |
| catalyst / institution / op_leverage / partnership / insider / narrative | NUMERIC | 各因子分 |
| gate_passed | BOOLEAN | [v1.1] 是否過催化劑 Gate(§7.4)，前端兩級呈現用 |
| veto_flags | TEXT[] | 非空 = 不可買 |
| data_gaps | TEXT[] | [v1.1 實作補充] 缺資料註記（如 institution 未就緒、cash_runway 抓不到），與 veto 區分——缺資料不否決 |
| PK | (ticker, score_date) | |

### 3.4 `track_record`(誠信 guidance 兌現率)
| 欄位 | 型別 | 說明 |
|---|---|---|
| ticker | TEXT | |
| promise_date | DATE | |
| promise_text | TEXT | |
| promise_deadline | DATE | |
| verified | BOOLEAN | NULL=未到期或待核，由 §7.6 驗證 job 填 |
| verify_date | DATE | |
| verify_method | TEXT | [v1.1] 'llm' \| 'manual' |

兌現率 = COUNT(verified=true) / COUNT(verified IS NOT NULL) WHERE deadline < today。樣本 ≥4 才啟用為 veto。

### 3.5 `universe_snapshot`([v1.1] 回測資產，見 §9)
| 欄位 | 型別 | 說明 |
|---|---|---|
| snapshot_date | DATE | |
| ticker | TEXT | |
| market_cap / adv_dollar / close | NUMERIC | 當日值 |
| PK | (snapshot_date, ticker) | |

只存 L0 通過者（≤3,500 列/日，每列 ~50B → 一年 ~60MB）。若逼近容量，改存壓縮 CSV 至 repo `data/`。

**空間預算**：events 一年 <5 萬列、每列 <1KB，不存公告全文 → 一年 <50MB；加 universe_snapshot 一年 <120MB，免費層撐 3 年+，容量監控見 §8.3。

---

## 4. L0 — yfscreen 粗篩條件

### 4.1 能做 / 不能做的界線(必須遵守)
| screener **能**篩 | screener **不能**篩(落到 L1) |
|---|---|
| region、市值、成交量(股數)、單期營收成長、PE/PB/PS | 任何均線(MA)、均線幾何關係、多年 CAGR、OBV、RS Line、距52週高低、成交「額」 |

> Yahoo screener 沒有均線欄位，`價格 > MA20` 這類條件 yfscreen 做不到。實作前先跑 `yfs.data_filters` 印出當前環境實際可用欄位名核對(Yahoo 偶爾改名)。

### 4.2 L0 條件(左右共用硬門檻 + 各自成長門檻)
| 條件 | 左池 | 右池 |
|---|---|---|
| region | us | us |
| 市值 | **$150M – $20B** | **$150M – $20B** |
| 最新價 | ≥ $2 | ≥ $2 |
| 日成交量(股數，粗) | > 500,000 | > 500,000 |
| 單期營收 YoY | **≥ 0%(放鬆，見註)** | ≥ 20% |

**左池營收放鬆的理由**：左側初期標的財報通常還沒顯現(RKLB/NBIS 進場時財報都難看)。左池不靠基本面篩，靠 L2 催化劑當真正過濾器。**代價是必須在 L2 把左池催化劑門檻收到 specificity≥4 來補償**(見 §7.4)。

> [v1.1] 市值範圍由使用者拍板 $150M–$20B（左右池同）。下限 $150M 保留，擋 nano-cap 操縱股（另有 L1 adv_dollar ≥ $2M 流動性底線）。

### 4.3 [v1.1] 量級與批次策略（$20B 上限的直接後果）

$150M–$20B + 量>500K 估 universe **2,500–3,500 檔**，L1 逐檔拉歷史價的量級規劃：

- **增量 cache**：日線快取存 repo `data/dual_pool/ohlcv/`（或 Actions cache），每晚只拉最新 1–5 日補洞；僅新進 universe 的 ticker 才全量拉 400 日。
- **分批 + 限速**：每批 ≤200 檔，批間 sleep；yfinance 失敗重試上限 2 次，仍失敗 → 記入 `data_gap` 清單跳過，**不得讓單檔失敗中斷整批**。
- **超時降級**：L1 總時限 90 分鐘；超時則只處理「昨日已在池 + 今日 L0 新出現」的檔，其餘順延次日。
- **首跑（冷啟動）**：全量 3,500 檔 × 400 日一次拉完可能超時，允許分 2–3 晚完成，完成前 watchpool 標記 warming_up。

---

## 5. L1 — 形態識別(本地計算，系統核心)

**這一層 screener 全做不到，必須用 yfinance 逐檔拉歷史價自己算。左右分池的真正邏輯在這裡。**

### 5.1 需計算的特徵(每檔)
拉近 400 個交易日日線(auto_adjust)，歷史 <200 日者資料不足、丟棄。計算：

| 特徵 | 定義 | 用途 |
|---|---|---|
| MA5/20/60/120/200 | 收盤價各期簡單均線最新值 | 基礎 |
| **entangle(長均線糾纏度)** | (max−min)/mean of {MA60,MA120,MA200} | 小=三條擠一起=底部盤整；大=發散=趨勢在走 |
| **slope200** | (MA200今 − MA200 20日前)/MA200 20日前 | 近0=走平(左)；明顯正=上揚(右)；負=排除 |
| dist_low | (價−52週低)/52週低 | 距底部多遠 |
| dist_high | (52週高−價)/52週高 | 距高點多遠 |
| ext(延伸度) | 價/MA200 − 1 | 相對長均線拉多高 |
| adv_dollar | 近20日 (收盤×成交量) 平均 | **成交額**流動性，非股數 |
| vol_ratio | 近5日均量 / 近60日均量 | 左要溫和、右要放量 |
| reclaimed_short | 價>MA5 且 價>MA20 | 拐頭確認 + 崩盤地板 |
| bull_align | MA5>MA20>MA60>MA120>MA200 | 多頭排列 |

### 5.2 ★ 重要形態事實(必須寫進實作註解)
**長期盤整剛翻上時，價格是「穿過」低位糾纏的長均線群往上，不是待在它們下面。** 因此「價格 ≤ MA120/MA200」是錯的門檻——那卡在「還沒拐頭」的過早階段。經合成資料驗證，真正能分辨左側初期的判別子是：**長均線糾纏度 + 長均線走平 + 距52週低近 + 已收復短均線**，不是「價格在長均線下」。

### 5.3 左池判定(左側初期)—— 全部條件 AND
| # | 條件 | 門檻 | 意義 |
|---|---|---|---|
| 1 | adv_dollar ≥ | **$2,000,000** | 流動性底(自營建部位硬底) |
| 2 | reclaimed_short = | **True** | 崩盤地板(硬，不可關)：已站上 MA5+MA20 |
| 3 | entangle ≤ | **0.06** | 長均線糾纏(盤整夠緊) |
| 4 | slope200 ≥ | **−0.02** | 長均線走平，不在跌 |
| 5 | dist_low ≤ | **0.40** | 還在底部區(距52週低 ≤40%) |
| 6 | ext ≤ | **0.25** | 未過度延伸(還早，價/MA200−1 ≤25%) |
| 7 | vol_ratio ≤ | **2.0** | 量能溫和(爆量代表已被發現→出場非進場) |

> 驗證結果：左側初期合成型態 entangle=0.04 / slope=+0.01 / distLow=13% → 判為 LEFT ✓；
> 崩盤型態因 reclaimed_short=False 被條件2擋掉 → 不進任何池 ✓。

### 5.4 右池判定(右側動能)—— 全部條件 AND
| # | 條件 | 門檻 | 意義 |
|---|---|---|---|
| 1 | adv_dollar ≥ | $2,000,000 | 流動性底 |
| 2 | bull_align = | True | 多頭排列已成 |
| 3 | entangle ≥ | 0.06 | 長均線發散(趨勢在走) |
| 4 | dist_low ≥ | 0.30 | 已離開底部 |
| 5 | slope200 ≥ | 0.015 | 長均線上揚 |
| 6 | vol_ratio ≥ | 1.2 | 突破帶量 |

### 5.5 右池可選品質閘門(5年 CAGR)—— 預設關閉
| 條件 | 門檻 |
|---|---|
| 5年營收 CAGR ≥ | 15% |
| 5年 EPS CAGR ≥ | 10% |

**⚠️ 取捨(必須寫進註解)**：此閘門會**結構性排除近年 IPO/SPAC**——太空/AI硬體最新敘事沒有5年乾淨數據。想要品質就開，想抓最新黑馬就關。歷史不足5年者**回傳通過(不誤殺)**，交給 L2 催化劑層判斷。**左池絕不套用此閘門**(左側初期本來就還沒有 CAGR，卡了會排除 RKLB 型標的)。

### 5.6 分池規則、遲滯與畢業機制
```
對每個 candidate：
  算 features
  若 is_left_early     → 進左池
  elif is_right_momentum 且 通過(可選)CAGR → 進右池
  else → 丟棄(還在崩/還沒拐/中段不上不下)
```

**[v1.1] 互斥保證來自判定順序，不是條件本身**：entangle=0.06 恰好同時滿足左 ≤0.06 與右 ≥0.06。上述先判左的順序解掉邊界重疊——**此事實必須寫進實作註解**，改判定順序 = 改行為。

**[v1.1] 遲滯機制（防 churn）**：
- 進池後**保留至少 10 個交易日**（`entered_at` 起算），期間形態條件失守不踢出，僅標 `liquidity_ok=false`（若失守的是 adv_dollar）。
- 10 日後仍不滿足進池條件 → 移出。
- 例外立即移出：觸發任一 veto（§7.5）、adv_dollar 連續 5 日 < $2M、或左池畢業轉右池。
- 移出後**冷卻 5 個交易日**才可重進，防單日邊界震盪。
- [v1.1 實作補充] right→left 重分類走 remove + cooldown：動能瓦解退回盤整形態 = 移出，冷卻 5 交易日後若仍判左才進左池（不無縫轉池；與左→右畢業的「立即」不對稱是設計行為）。

**畢業機制自動成立**：一檔從左池站穩多頭排列後，下次批次會落到右池——這是把左側核心倉轉成右側動能倉的減倉信號，不是新開倉，避免重複追高。畢業不受 10 日保留限制。

### 5.7 待驗證
Yahoo 欄位名(§4.1)；L1 所有門檻（含 [v1.1] 遲滯的 10 日/5 日）為起始值，**回測校準後才定案**(見 §9)。

---

## 6. L2 — 催化劑抽取(EDGAR + LLM)

**定位：LLM 是抽取器不是搜尋器。** 先用 EDGAR 把公告拉下來，把「單份公告純文字」餵給 LLM，它把非結構化文本變成 JSON 欄位。它不會自己去找催化劑。

### 6.1 EDGAR 抓取範圍
| 項目 | 規格 |
|---|---|
| 標的 | 只抓 watchpool(左+右)內 ticker，非全市場 |
| 文件 | 8-K(含附件 PR)、Form 4(內部人)；13F 另走 §6.9 季度管線 |
| 增量 | 每日夜間拉前一日新申報；初次上線回補近 90 日 |
| Header | 必帶 `User-Agent: BamHI research <contact>` |
| 限速 | ≤10 req/s(實務 1 req/s) |
| Item 解析 | 抓 8-K 的 Item 編號，作為事件類型強先驗 |

Item→類型先驗：1.01=重大協議(new_contract)、2.02=業績(guidance)、3.02=未登記股權出售(dilution)、5.02=高管異動、7.01=Reg FD、8.01=其他。

### 6.2 規則過濾(進 LLM 前淘汰噪音)
用 Item 編號先淘汰純行政公告(例行 8.01 無實質、純程序性揭露)。只把可能含催化劑的送 LLM，壓低配額消耗。

### 6.3 LLM 抽取契約
**System prompt 要點**(英文，因讀英文公告)：
- 角色：小市值事件系統的財經事件抽取引擎，不給意見/目標價/建議
- 只抽原文明示資訊，**禁止推論/估算/用外部知識補**，抽不到填 null
- **只輸出 JSON，無 markdown 圍欄、無前言**
- 一份公告可含多事件→陣列；可含零事件→空陣列
- 區分 binding vs non-binding："definitive agreement/signed/purchase order"=binding；"MOU/LOI/exploring/strategic partnership 無條款"=non-binding。此區分驅動 specificity
- 標記負面事件(增發/重述/換審計師/財測下修/going concern)——與正面催化劑同等重要
- [v1.1] `headline` 與 `evidence_anchor` 之外的自由文字欄位**輸出繁體中文**；`evidence_anchor` 保留原文逐字

**輸出欄位**(每事件)：
| 欄位 | 說明 |
|---|---|
| event_type | 見 §6.4 枚舉，擇一最佳 |
| headline | 中立一句 ≤20 字，**繁體中文**，禁形容詞 |
| counterparty | 具名對手方，無則 null |
| counterparty_tier | 見 §6.5 |
| magnitude_usd | 明示金額，否則 null，禁自算 |
| magnitude_pct_rev | 明示佔營收比才填，禁自算 |
| timeline_months | 距兌現月數，否則 null |
| is_recurring | 持續/多年收入=true |
| specificity | 1–5，見 §6.6 |
| direction | bullish \| bearish \| neutral |
| is_integrity_flag | 重述/換審計師/going concern/重大缺失/高管非常規離職 |
| is_dilution_flag | 增發/ATM/shelf S-3/可轉債/認股權證 |
| evidence_anchor | ≤15字逐字錨句(原文語言)，審計用 |
| confidence | 0–1 |

外層另有 `filing_summary`(≤25字)。`extraction_method` 由程式端填非 LLM 輸出。

### 6.4 event_type 枚舉
- 正面：new_contract, new_client, new_product, market_entry, policy_beneficiary, guidance_raise, capacity_expansion, strategic_investment, mna_target, backlog_growth, regulatory_approval, insider_buy
- 前瞻(另寫入 track_record)：guidance, commitment
- 負面/風險：dilution_offering, guidance_cut, insider_sell, restatement, auditor_change, going_concern, litigation, customer_loss, other_negative
- 兜底：other

### 6.5 counterparty_tier 規則
- **tier1_giant**：超大市值錨定客戶或頂級政府機構。例：Apple、NVIDIA、Microsoft、Amazon、Google/Alphabet、Meta、Broadcom、TSMC、Samsung、主要 hyperscaler、美國 DoD/NASA/DOE、前三大車廠、頂級藥廠
- **tier2**：具名的成熟中大型上市公司，非超大市值
- **unknown**：未具名、私人、小型

### 6.6 specificity 1–5 評分規則(單調遞增，取最強事件條款)
| 分 | 條件 |
|---|---|
| 1 | 空話：非綁定、無具名、無數字("strategic partnership"，"exploring") |
| 2 | 具名對手方，但無財務條款、無日期 |
| 3 | 具名 + 一個硬條件(金額 或 具體日期/期間) |
| 4 | 具名 + 金額 + 日期或期間 |
| 5 | 具名 + 金額 + 日期 + 綁定/definitive 且/或 明確多年recurring |

### 6.7 Fallback 規則引擎(LLM 全掛時，extraction_method='rule')
- Item 編號 → event_type 映射
- 正則抓金額 `\$[\d,.]+ ?(M|B|million|billion)`、日期 `Q[1-4] 20\d\d`
- tier1 字典比對(§6.5 名單小寫)
- specificity **封頂 3**(規則抓不準 binding/recurring)
- is_dilution_flag：正則 `offering|ATM|shelf|convertible|warrant`

### 6.8 版權/儲存
不存公告全文；evidence_anchor 限 ≤15 字。8-K 本體是申報文件，但附件 PR 為公司著作，不得整段入庫。

### 6.9 [v1.1] 13F 機構持倉管線（institution 因子資料源）

**v1.0 漏掉的整條管線。** 13F 是機構申報的，不是公司申報——「ticker X 有幾家新進機構」無法從公司的 EDGAR 頁取得，必須反向建索引：

| 項目 | 規格 |
|---|---|
| 資料源 | SEC 官方 13F 結構化資料集（季度 bulk，Form 13F data sets）；備援：EDGAR full-text 逐檔（慢） |
| 頻率 | 季度 job（13F 截止日 = 季後 45 天；截止日後一週內跑） |
| 處理 | 下載整季 bulk → 過濾出 watchpool 內曾出現過的 ticker（依 CUSIP 對映）→ 對每 ticker 算「本季新出現的機構 filer 數」（上季無持倉、本季有） |
| 落庫 | `institution_quarterly` 表：(ticker, quarter, new_holders, total_holders, known_at=filing 截止後實跑日) |
| point-in-time | known_at 用 **filing date**（非 period date），與 §8.2 一致 |

**已知限制（必記入實作註解）**：45 天申報延遲對右池「快進快出」是時效錯配——institution 因子反映的是 1.5–4.5 個月前的持倉。右池權重 0.20 是在餵舊資料，回測歸因（§9）要單獨檢視此因子對右池是否有效，無效就把權重移給 narrative/catalyst。

---

## 7. L3 — 評分計分卡

### 7.1 量綱與告警
total ∈ **0–100**。六因子各歸一化 0–1，加權和 ×100。告警：`total(T) − total(T−1) > 15` → 推播(沿用現有 Discord webhook)。

### 7.2 六因子定義
| 因子 | 定義 |
|---|---|
| catalyst | 見 §7.3 |
| institution | 13F 新進機構數 percentile(母體=同池同市場)，資料源見 §6.9 |
| op_leverage | ΔEPS%/ΔRev% 分段給分；或毛利率連續走揚季數 |
| partnership | counterparty_tier 加權：tier1=1.0 / tier2=0.6 / unknown=0.2 |
| insider | [v1.1] **近 90 日 Form 4 淨買入金額 / 當前市值**，同池 percentile。淨買入 = Σ(公開市場買進) − Σ(公開市場賣出)，排除選擇權行使自動賣出(10b5-1 標記者減半計) |
| narrative | 板塊 RS percentile(用現有 sector_rotation 的 rs_rank) |

**op_leverage 分段**：ΔEPS%/ΔRev%(需 ΔRev>0)：<1→0，1–2→0.4，2–3→0.7，>3→1.0。或毛利率走揚：1季→0.3，2季→0.7，≥3季→1.0。兩者取 max。ΔRev≤0 或 EPS由負轉正時只用毛利率。

### 7.3 catalyst 因子算法(規格)
```
active = 篩選 events 中 direction=bullish 且未過期者
         (過期天數：is_recurring ? 180 : 90，以 known_at 計)
若 active 為空 → catalyst = 0
單事件分 one(e)：
  base   = specificity / 5
  decay  = timeline_months 為 null ? 1 : max(0, 1 − timeline_months/12)
  tier   = {tier1_giant:1.3, tier2:1.05, unknown:1.0}
  rec    = is_recurring ? 1.3 : 1.0
  one(e) = min(1.0, base × decay × tier × rec)
catalyst = min(1.0, max(one(e)) + 0.1 × (active事件數 − 1))   # 取最強 + 密度小獎勵
```

> [v1.1 已知簡化] decay 用抽取當下的 timeline_months 固定值，事件擺著不會隨兌現日逼近而變化，只有 90/180 天到期懸崖。可接受，先不改；回測若顯示過期懸崖造成分數跳水誤導，再改成隨日重算。

### 7.4 左右權重表 + Gate（[v1.1] 明定為顯示層過濾）
| 因子 | 左池權重 | 右池權重 |
|---|---|---|
| catalyst | **0.30** | 0.20 |
| op_leverage | 0.25 | 0.15 |
| institution | 0.20 | 0.20 |
| partnership | 0.10 | 0.15 |
| insider | 0.10 | 0.10 |
| narrative | **0.05** | **0.20** |

**設計理由**：左池壓低 narrative(要在板塊還沒熱時進)、拉高 catalyst+op_leverage(前瞻性)；右池拉高 narrative(順已成共識)。

**Gate(催化劑門檻，補償形態寬鬆)**：
- 左池：direction=bullish 且 **specificity≥4** 且 (timeline_months 為 null 或 ≤6)
- 右池：direction=bullish 且 specificity≥3

**[v1.1] Gate 語意明定**：Gate **不影響 watchpool 成員資格**（那是 L1 的事），是**顯示層第三過濾**。scores 表每檔照算並填 `gate_passed`。前端兩級呈現：
- **候選清單**：`gate_passed=true` 且 veto_flags 為空 — 可行動名單
- **池內觀察**：其餘池內標的，照分數排序 — 等催化劑落地

左池 specificity≥4 事件在小型股很稀有，候選清單可能常態很短甚至空——**這是設計行為不是 bug**（左側形態刻意放寬 → 用 Gate 嚴收窄），兩級呈現就是為此而設。

### 7.5 veto 層(一票否決，不進加權)
| 旗標 | 觸發條件 | [v1.1] 時間窗 |
|---|---|---|
| integrity | 任一 event 的 is_integrity_flag=true | 近 **365 天**內 |
| dilution | 任一 event 的 is_dilution_flag=true | 近 **180 天**內 |
| cash_runway | 現金及約當現金 / 季燒錢 < 2 季 | 最新財報 |
| guidance_missed | track_record 兌現率 < 0.5(樣本≥4) | 全歷史 |
| liquidity | adv_dollar 跌破 $2M | 當日 |

**[v1.1] cash_runway 定義**：季燒錢 = |TTM operating cash flow| / 4，僅當 TTM operating CF < 0 才評估（正現金流無跑道問題）。資料源 yfinance 財報；**缺資料 → 略過此 veto 並在 scores 附註 `data_gap:cash_runway`**，不得把缺資料當否決。

veto_flags 非空 → 該檔標記不可買，分數照算但前端標紅。

### 7.6 [v1.1] track_record 驗證管線（v1.0 缺的閉環）

沒有這條，`verified` 永遠是 NULL，guidance_missed veto 永不觸發：

| 項目 | 規格 |
|---|---|
| 頻率 | 每週一次（併入週末批次） |
| 對象 | track_record 中 `deadline < today` 且 `verified IS NULL` 的 promise |
| 方法 | 拉該 ticker deadline 前後 45 天的 events + 最近一季財報摘要 → LLM 判定 promise 是否兌現（prompt 同 §6.3 紀律：只依提供材料，判不出 → 回 `unknown`） |
| unknown 處理 | 保持 NULL，累計 2 次 unknown → 寫入人工待核佇列（前端小表），人工填 verified + verify_method='manual' |
| 落庫 | verified / verify_date / verify_method |

---

## 8. 編排與排程

### 8.1 cron(UTC，含延遲容忍)
| 邏輯時間 TPE | cron UTC | 內容 |
|---|---|---|
| 06:00 | `0 22 * * *` | 美股 L0→L1→L2→L3 全鏈（**[v1.1] 美股收盤後**） |
| 週六 08:00 | `0 0 * * 6` | §7.6 track_record 驗證 + §8.3 用量檢查 |
| 季度(13F 截止後) | 手動觸發或 2/15、5/15、8/15、11/15 | §6.9 13F 索引 job |

> [v1.1] v1.0 的 13:00 UTC(21:00 TPE) 是美東盤前 09:00，拉到的日線是 T-1 收盤，形態信號慢一個 session。改 22:00 UTC = 美東 17:00/18:00（冬/夏令），當日收盤與盤後 8-K 都齊。known_at 規則（§8.2）同步改。

GitHub Actions cron 可延遲 30 分鐘+，所有批次**冪等**(以 run_date 為鍵，重跑不重複寫)。L3 用「資料完備性檢查」而非時間假設決定是否執行。

### 8.2 Point-in-time 紀律(回測與實盤一致)
- events.known_at 記系統得知時間；回測只用 `known_at < 當日` 的事件
- 13F：known_at = filing date(非 period date)
- 回測 known_at 定義：公告發布日**次日 06:00 TPE**（= 系統批次實跑時點）才可知；最早執行 = 次一交易日開盤

### 8.3 免費層監控
GitHub Actions 分鐘、Supabase 容量、LLM 每日配額 各加用量檢查，>70% 告警。Supabase 7天無活動會暫停 → daily cron 天然保活 + heartbeat step。

---

## 9. 回測規格(上線前 Go/No-Go 閘門)

| 項目 | 規格 |
|---|---|
| Universe | [v1.1] 見下方「universe 現實約束」 |
| 重放 | 每月月初，只用 known_at<當日 的事件算分 |
| 抽取 | 歷史公告**一律走規則引擎**(§6.7)；LLM 僅對 top decile 樣本抽查敏感度 |
| 驗證指標 | top decile vs bottom decile 後 60 日超額報酬 spread(對板塊等權基準) |
| 通過門檻 | spread 年化 >8% 且 3年中至少2年為正 |
| 因子歸因 | 逐一關閉每因子重跑，找貢獻來源；[v1.1] 特別檢視 institution 對右池（§6.9 時效錯配） |

**[v1.1] Universe 現實約束（取代 v1.0 的「當日行情快照建 universe」）**：
v1.0 要求回測含已下市/被併股，但行情源是 yfinance——**下市股歷史拉不到，免費層無法回溯建 3 年無偏 universe**。修正為兩段：
1. **回溯段（上線前回測）**：用現存股票 + EDGAR 歷史申報，**明記倖存者偏差為已知限制**——它會高估絕對報酬，但對 top-vs-bottom decile 的「相對」spread 影響較小（兩端同受偏差）。報告必須寫明此限制。
2. **前瞻段（上線後）**：§3.5 `universe_snapshot` 每日落庫，從上線日起累積無偏 point-in-time universe。6 個月後用 forward 資料複驗 spread，這才是可信的最終驗證。

**閘門紀律：spread 拉不開 → 回頭改 L1 門檻/L3 權重，不帶未驗證的計分卡上線。**

---

## 10. 關鍵紀律與取捨(必須落實到實作)

1. **左側是報酬最高、勝率最低的位置**：十檔可能七檔鈍住。成敗不在篩網，在(a) L2 催化劑當領先信號濾出「要爆的底」vs「還沒跌完的底」，(b) 極嚴停損砍掉鈍住的。左池形態寬 + 催化劑嚴 + 停損嚴，三者綁定。
2. **風險預算**：左池持有久、部位大，基本面卻放鬆——這是刻意的，但必須用催化劑 Gate(specificity≥4)+ 現金跑道 veto + 停損紀律三條下游閘門補償。缺一不可。
3. **右側篩網本身無 alpha**：與市面 CANSLIM/Minervini 高度重疊，產出多為已知名字。差異化在下游催化劑時點與部位管理，別指望右側篩網給優勢。
4. **5年 CAGR 的取捨**：開=品質但排除新IPO；關=抓最新黑馬但混入低質。預設關，右池想升級品質再開。左池永不套用。
5. **崩盤地板不可關**：reclaimed_short 是唯一能把左側初期與接刀分開的條件。

---

## 11. 待決定 / 待驗證清單

**待決定(需人拍板)**
| 項 | 狀態 |
|---|---|
| 市值範圍 | ✅ 已定 $150M–$20B（v1.1） |
| 右池是否開 5年CAGR | 預設關 |
| MVP 範圍 | 見 §12 |
| 頁名「小市值策略」vs $20B 範圍 | 待使用者決定是否改名 |

**待驗證(實作首週實測)**
| 項 | 方式 |
|---|---|
| Yahoo screener 欄位名 | 跑 `yfs.data_filters` 核對 |
| Gemini 免費層當前 RPD/RPM | 官方文件 + 實測 |
| EDGAR User-Agent 是否被限 | 首日抓取實測 |
| SEC 13F bulk 資料集格式/CUSIP 對映 | §6.9 首次季度 job 實測 |
| L1 全量 3,500 檔的實際 runtime | §4.3 首跑實測 |
| L1 所有門檻 | §9 回測校準 |

---

## 12. 施工順序建議(MVP 優先)

| 階段 | 內容 | Go/No-Go |
|---|---|---|
| 1 | L0+L1(yfscreen 粗篩 + 本地形態 + §4.3 批次/cache + §5.6 遲滯，輸出左右兩池 → watchpool 表 + universe_snapshot) | 兩池數量合理(左 20–60、右 10–30) |
| 2 | L2 EDGAR 抓取 + 規則過濾 + LLM 抽取 → events 表 | 抽取 JSON 穩定率 >95% |
| 3 | L3 計分卡 + veto + Gate 兩級呈現 + 前端頁 | 分數可歸因 |
| 4 | 回測(§9 回溯段)→ spread 驗證 | **spread 年化 >8% 才續** |
| 5 | 13F 季度 job(§6.9) + track_record 驗證 job(§7.6) | institution/guidance veto 啟用 |
| 6 | 通過則複製台股版(換 MOPS 數據源 + 中文 prompt，schema/邏輯不動) | |

**里程碑鐵律：第4階段回測是硬閘門。** 前3階段可先跑起來看數據，但沒過 spread 門檻不進實盤、不上台股。

> [v1.1] 13F/track_record 移到階段 5：兩者都不擋 MVP（institution 因子未就緒前權重暫移給 catalyst +0.10、narrative +0.10，scores 附註 `data_gap:institution`；guidance_missed veto 樣本不足本來就不啟用）。

---

## 附：與現有 BamHI 整合點
- Supabase 讀寫沿用 `backend/services/insider.py` 的 lazy-init + service key 模式(env: SUPABASE_URL / SUPABASE_SERVICE_KEY)
- 前端唯一 HTTP 出口走 FastAPI router(照現制，不開 anon key 直連；HTTP 統一走 `frontend/src/api/client.js`)
- narrative 因子直接用 `backend/services/sector_rotation.py` 的 rs_rank
- GitHub Actions 走 `seed_insider.yml` 範式(直寫 Supabase 不 commit)
- 新頁三件套：`backend/routers/` + `frontend/src/router/index.js` `/app/*` 子路由 + `TopNav.vue` 交易工具下拉
- LLM key 只放 GitHub Actions secrets + backend/.env(gitignored)，任何檔案不得出現 key 本體；建議加 gitleaks pre-commit
