"""
views/_sector_charts.py  v2
"""
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st


def get_rrg_quadrant(rs_ratio: float, rs_momentum: float) -> tuple:
    if rs_ratio > 100 and rs_momentum > 100:
        return "🟢 領先 Leading",   "#22c55e", "強勢加速，主升段核心板塊"
    elif rs_ratio > 100 and rs_momentum <= 100:
        return "🟡 轉弱 Weakening", "#eab308", "強勢但動能減速，注意高點風險"
    elif rs_ratio <= 100 and rs_momentum <= 100:
        return "🔴 落後 Lagging",   "#ef4444", "弱勢且加速惡化，建議觀望"
    else:
        return "🔵 改善 Improving", "#3b82f6", "弱勢但動能回升，潛在輪動候選"


def _rrg_base_shapes() -> list:
    """四象限背景色塊"""
    return [
        dict(type="rect", xref="x", yref="y", x0=100, x1=150, y0=100, y1=150,
             fillcolor="rgba(34,197,94,0.07)",  line_width=0, layer="below"),
        dict(type="rect", xref="x", yref="y", x0=100, x1=150, y0=50,  y1=100,
             fillcolor="rgba(234,179,8,0.07)",  line_width=0, layer="below"),
        dict(type="rect", xref="x", yref="y", x0=50,  x1=100, y0=50,  y1=100,
             fillcolor="rgba(239,68,68,0.07)",  line_width=0, layer="below"),
        dict(type="rect", xref="x", yref="y", x0=50,  x1=100, y0=100, y1=150,
             fillcolor="rgba(59,130,246,0.07)", line_width=0, layer="below"),
    ]


def _rrg_base_annotations() -> list:
    return [
        dict(x=148, y=148, text="<b>領先 Leading</b>",   showarrow=False,
             font=dict(color="#22c55e", size=12), xanchor="right", yanchor="top"),
        dict(x=148, y=52,  text="<b>轉弱 Weakening</b>", showarrow=False,
             font=dict(color="#eab308", size=12), xanchor="right", yanchor="bottom"),
        dict(x=52,  y=52,  text="<b>落後 Lagging</b>",   showarrow=False,
             font=dict(color="#ef4444", size=12), xanchor="left",  yanchor="bottom"),
        dict(x=52,  y=148, text="<b>改善 Improving</b>", showarrow=False,
             font=dict(color="#3b82f6", size=12), xanchor="left",  yanchor="top"),
    ]


def _rrg_layout(fig: go.Figure, height: int = 520):
    fig.add_hline(y=100, line_dash="dash", line_color="rgba(255,255,255,0.2)")
    fig.add_vline(x=100, line_dash="dash", line_color="rgba(255,255,255,0.2)")
    fig.update_layout(
        template="plotly_dark",
        shapes=_rrg_base_shapes(),
        annotations=_rrg_base_annotations(),
        xaxis=dict(title="RS-Ratio（強度）", range=[50, 150],
                   showgrid=True, gridcolor="#30363d"),
        yaxis=dict(title="RS-Momentum（動能）", range=[50, 150],
                   showgrid=True, gridcolor="#30363d"),
        height=height,
        margin=dict(l=40, r=40, t=30, b=40),
        plot_bgcolor="rgba(22,27,34,0.95)",
        paper_bgcolor="rgba(0,0,0,0)",
    )


# ── RRG 即時快照（使用預計算字典，避免 Tab 殘留問題）──────────────────────────
def render_rrg_tab(sector_data_dict: dict):
    """
    sector_data_dict: {sector_name: df_sector}  預先計算好的資料字典
    """
    st.subheader("📡 RRG 板塊輪動圖 (Relative Rotation Graph)")
    st.caption("X 軸 RS-Ratio > 100 = 強勢｜Y 軸 RS-Momentum > 100 = 加速｜Hover 看板塊名稱")

    rows = []
    for s_name, df_sec in sector_data_dict.items():
        valid = df_sec.dropna(subset=['RS_Ratio', 'RS_Momentum'])
        if valid.empty:
            continue
        last = valid.iloc[-1]
        rs_r, rs_m = float(last['RS_Ratio']), float(last['RS_Momentum'])
        q_label, color, q_desc = get_rrg_quadrant(rs_r, rs_m)
        rows.append(dict(Sector=s_name.split(" ")[0], FullName=s_name,
                         RS_Ratio=round(rs_r, 2), RS_Momentum=round(rs_m, 2),
                         Quadrant=q_label, Color=color, Desc=q_desc))

    if not rows:
        st.warning("資料不足，請選擇更長區間（建議 2y 以上）。")
        return

    df_rrg = pd.DataFrame(rows)
    fig = go.Figure()

    for _, row in df_rrg.iterrows():
        # 板塊名稱縮寫（取第一個詞）
        short_label = row['FullName'].split(" ")[0]
        fig.add_trace(go.Scatter(
            x=[row['RS_Ratio']], y=[row['RS_Momentum']],
            mode="markers+text",
            text=[short_label],
            textposition="top center",
            textfont=dict(color=row['Color'], size=10),
            marker=dict(size=14, color=row['Color'],
                        line=dict(color='white', width=1.5)),
            name=row['FullName'],
            hovertemplate=(
                f"<b>{row['FullName']}</b><br>"
                f"RS-Ratio: {row['RS_Ratio']:.2f}<br>"
                f"RS-Momentum: {row['RS_Momentum']:.2f}<br>"
                f"象限: {row['Quadrant']}<extra></extra>"
            ),
            showlegend=False,
        ))

    _rrg_layout(fig)
    st.plotly_chart(fig, use_container_width=True)

    # 排行榜表格
    st.markdown("**📋 各板塊 RRG 即時排行（依 RS-Ratio 強弱排序）**")
    df_table = df_rrg[['FullName','RS_Ratio','RS_Momentum','Quadrant','Desc']].copy()
    df_table.columns = ['板塊', 'RS-Ratio', 'RS-Momentum', '象限', '解讀']
    df_table = df_table.sort_values('RS-Ratio', ascending=False).reset_index(drop=True)
    st.dataframe(df_table, use_container_width=True, hide_index=True,
                 column_config={
                     "RS-Ratio":    st.column_config.NumberColumn(format="%.2f"),
                     "RS-Momentum": st.column_config.NumberColumn(format="%.2f"),
                 })
# ── RRG 軌跡（Trail）Tab：接受預計算字典 ─────────────────────────────────────
def render_rrg_trail_tab(sector_data_dict: dict, trail_days: int = 10):
    """
    sector_data_dict: {sector_name: df_sector}  預先計算好的資料字典
    使用動態軸範圍 + 圖上板塊名標籤 + 詳細趨勢方向表格
    """
    st.subheader("📈 RRG 板塊輪動軌跡（RRG Tail）")
    st.caption("每條軌跡線代表一個板塊的移動路徑，終點 = 最新位置，起點 = N 天前的位置")

    # 說明 RS_Ratio/RS_Momentum 的歷史來源
    st.info(
        "💡 **軌跡資料說明**：軌跡由 `RS_Ratio`（滾動 14 日均線÷50 日均線）及 `RS_Momentum`（RS_Ratio 的 14 日動能）計算，"
        "需要至少 **50 個交易日**以上的歷史才能產生完整軌跡。若軌跡過短，請將 📅 歷史區間調到 **2y 以上**。"
    )

    trail_days = st.slider(
        "顯示軌跡天數",
        min_value=5, max_value=20, value=trail_days, step=1,
        key="rrg_trail_days",
        help="顯示最近 N 天的 RS_Ratio / RS_Momentum 路徑。10天(2週)是標準用法。"
    )

    fig = go.Figure()
    all_rs_r, all_rs_m = [], []
    table_rows = []
    has_data = False

    for s_name, df_sec in sector_data_dict.items():
        valid = df_sec.dropna(subset=['RS_Ratio', 'RS_Momentum'])
        n_valid = len(valid)
        if n_valid < 2:
            continue

        # 取最多 trail_days 天的尾巴（若歷史不足就取全部）
        actual_days = min(trail_days, n_valid)
        tail = valid.iloc[-actual_days:]
        rs_r = tail['RS_Ratio'].values
        rs_m = tail['RS_Momentum'].values
        all_rs_r.extend(rs_r)
        all_rs_m.extend(rs_m)
        has_data = True

        cur_r,   cur_m   = float(rs_r[-1]), float(rs_m[-1])
        start_r, start_m = float(rs_r[0]),  float(rs_m[0])
        q_label, color, _ = get_rrg_quadrant(cur_r, cur_m)
        short = s_name.split(" ")[0]

        # ── 方向向量判斷 ──────────────────────────────────────────────────────
        dr = cur_r  - start_r
        dm = cur_m  - start_m
        if   dr > 0 and dm > 0: direction = "↗ 向領先象限加速"
        elif dr > 0 and dm < 0: direction = "↘ 向轉弱象限滑入"
        elif dr < 0 and dm > 0: direction = "↖ 向改善象限回升"
        else:                   direction = "↙ 向落後象限沉降"

        # ── 趨勢強度判斷 ──────────────────────────────────────────────────────
        magnitude = (dr**2 + dm**2) ** 0.5
        if magnitude >= 3:   strength = "🔥 強烈"
        elif magnitude >= 1: strength = "➡ 溫和"
        else:                strength = "⬤ 微幅"

        table_rows.append({
            "板塊":         s_name,
            "當前象限":     q_label,
            "移動方向":     direction,
            "趨勢強度":     strength,
            "RS-Ratio起終": f"{start_r:.1f} → {cur_r:.1f}",
            "RS-Ratio變化": f"{dr:+.2f}",
            "RS-Mom起終":   f"{start_m:.1f} → {cur_m:.1f}",
            "RS-Mom變化":   f"{dm:+.2f}",
            "軌跡天數":     f"{actual_days}/{trail_days} 天",
        })

        # ── 漸層軌跡線（透明度由淡→濃）─────────────────────────────────────
        n = len(rs_r)
        for i in range(n - 1):
            opacity = 0.15 + 0.85 * (i / max(n - 1, 1))
            fig.add_trace(go.Scatter(
                x=[rs_r[i], rs_r[i+1]],
                y=[rs_m[i], rs_m[i+1]],
                mode="lines",
                line=dict(color=color, width=2.5),
                opacity=opacity,
                showlegend=False,
                hoverinfo='skip',
            ))

        # ── 起點（半透明小點）──────────────────────────────────────────────
        fig.add_trace(go.Scatter(
            x=[start_r], y=[start_m],
            mode="markers",
            marker=dict(size=6, color=color, opacity=0.35,
                        line=dict(color='white', width=1)),
            showlegend=False, hoverinfo='skip',
        ))

        # ── 終點（大圓點 + 板塊名標籤）────────────────────────────────────
        fig.add_trace(go.Scatter(
            x=[cur_r], y=[cur_m],
            mode="markers+text",
            text=[short],
            textposition="top center",
            textfont=dict(color=color, size=10, family="Arial"),
            marker=dict(size=13, color=color,
                        line=dict(color='white', width=1.5)),
            name=s_name,
            hovertemplate=(
                f"<b>{s_name}</b><br>"
                f"RS-Ratio: {cur_r:.2f}<br>"
                f"RS-Momentum: {cur_m:.2f}<br>"
                f"方向: {direction}<br>"
                f"強度: {strength}<br>"
                f"軌跡: {actual_days} 天<extra></extra>"
            ),
            showlegend=False,
        ))

    if not has_data:
        st.warning("⚠️ 所有板塊的 RS_Ratio / RS_Momentum 均為 NaN，資料不足。請確認歷史區間 ≥ 2y。")
        return

    # ── 動態軸範圍（留 5 單位 padding，避免標籤被裁切）─────────────────────
    if all_rs_r:
        pad = 5
        x_min = max(50,  min(all_rs_r) - pad)
        x_max = min(150, max(all_rs_r) + pad)
        y_min = max(50,  min(all_rs_m) - pad)
        y_max = min(150, max(all_rs_m) + pad)
    else:
        x_min, x_max, y_min, y_max = 85, 130, 85, 130

    fig.add_hline(y=100, line_dash="dash", line_color="rgba(255,255,255,0.25)")
    fig.add_vline(x=100, line_dash="dash", line_color="rgba(255,255,255,0.25)")
    fig.update_layout(
        template="plotly_dark",
        shapes=_rrg_base_shapes(),
        annotations=_rrg_base_annotations(),
        xaxis=dict(title="RS-Ratio（強度）", range=[x_min, x_max],
                   showgrid=True, gridcolor="#30363d"),
        yaxis=dict(title="RS-Momentum（動能）", range=[y_min, y_max],
                   showgrid=True, gridcolor="#30363d"),
        height=560,
        margin=dict(l=40, r=40, t=30, b=40),
        plot_bgcolor="rgba(22,27,34,0.95)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── 趨勢方向詳細表格 ───────────────────────────────────────────────────
    if table_rows:
        st.markdown(f"#### 📋 各板塊 {trail_days} 日 RRG 移動方向摘要")
        st.caption("依 RS-Ratio 變化排序。正值＝強度上升（偏多），負值＝強度下滑（偏空）。")
        df_tbl = pd.DataFrame(table_rows)
        # 排序：RS-Ratio 變化由大到小
        df_tbl["_sort"] = df_tbl["RS-Ratio變化"].astype(float)
        df_tbl = df_tbl.sort_values("_sort", ascending=False).drop(columns="_sort").reset_index(drop=True)
        st.dataframe(
            df_tbl,
            use_container_width=True,
            hide_index=True,
            column_config={
                "板塊":         st.column_config.TextColumn("板塊",           width="medium"),
                "當前象限":     st.column_config.TextColumn("當前象限",       width="medium"),
                "移動方向":     st.column_config.TextColumn("移動方向",       width="medium"),
                "趨勢強度":     st.column_config.TextColumn("趨勢強度",       width="small"),
                "RS-Ratio起終": st.column_config.TextColumn("RS-Ratio 起→終", width="medium"),
                "RS-Ratio變化": st.column_config.TextColumn("Δ RS-Ratio",    width="small"),
                "RS-Mom起終":   st.column_config.TextColumn("RS-Mom 起→終",   width="medium"),
                "RS-Mom變化":   st.column_config.TextColumn("Δ RS-Mom",      width="small"),
                "軌跡天數":     st.column_config.TextColumn("軌跡天數",       width="small"),
            }
        )


# ── 板塊相關係數熱力圖（使用預計算字典，避免 Tab 殘留問題）──────────────────
def render_correlation_heatmap(sector_data_dict: dict):
    """
    sector_data_dict: {sector_name: df_sector}  預先計算好的資料字典
    """
    st.subheader("🔗 板塊相關係數矩陣 (Inter-Sector Correlation)")
    st.caption("相關係數接近 +1 = 同漲同跌（不分散）｜接近 0 = 獨立輪動（有對沖效果）｜接近 -1 = 反向走勢（天然對沖）")

    series_dict = {}
    for s_name, df_sec in sector_data_dict.items():
        if 'Sector_Close' in df_sec.columns:
            short = s_name.split(" ")[0]
            series_dict[short] = df_sec['Sector_Close']

    if len(series_dict) < 2:
        st.warning("板塊資料不足，無法計算相關矩陣。")
        return

    with st.spinner("正在計算跨板塊相關係數..."):

        df_all = pd.DataFrame(series_dict).pct_change().dropna()
        corr   = df_all.corr()

        # 文字標籤
        text_vals = corr.round(2).astype(str).values

        fig = go.Figure(go.Heatmap(
            z=corr.values,
            x=corr.columns.tolist(),
            y=corr.index.tolist(),
            text=text_vals,
            texttemplate="%{text}",
            textfont=dict(size=9),
            colorscale="RdBu_r",
            zmid=0,
            zmin=-1, zmax=1,
            colorbar=dict(title="相關係數", thickness=15),
            hoverongaps=False,
        ))
        fig.update_layout(
            template="plotly_dark",
            height=520,
            margin=dict(l=100, r=40, t=30, b=100),
            xaxis=dict(tickangle=-40, tickfont=dict(size=10)),
            yaxis=dict(tickfont=dict(size=10)),
            plot_bgcolor="rgba(22,27,34,0.95)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)

        # 找出相關係數最低的組合（最佳分散化對）
        # NumPy 2.x: DataFrame.values 是 read-only，需先取出可寫入的 numpy copy
        _corr_arr = corr.to_numpy(copy=True).astype(float)
        np.fill_diagonal(_corr_arr, np.nan)
        corr_no_diag = pd.DataFrame(_corr_arr, index=corr.index, columns=corr.columns)
        min_idx = np.unravel_index(np.nanargmin(_corr_arr), _corr_arr.shape)
        max_idx = np.unravel_index(np.nanargmax(_corr_arr), _corr_arr.shape)
        col_a, col_b = st.columns(2)
        with col_a:
            st.success(f"✅ 最佳分散對：**{corr.columns[min_idx[0]]}** × **{corr.columns[min_idx[1]]}**  \n"
                       f"相關係數 = {corr_no_diag.iloc[min_idx[0], min_idx[1]]:.2f}（同時持有風險最低）")
        with col_b:
            st.warning(f"⚠️ 高度重疊對：**{corr.columns[max_idx[0]]}** × **{corr.columns[max_idx[1]]}**  \n"
                       f"相關係數 = {corr_no_diag.iloc[max_idx[0], max_idx[1]]:.2f}（同時持有幾乎無分散效果）")


# ── 板塊寬度走勢圖（維持原版） ────────────────────────────────────────────────
def render_breadth_chart(df_sector: pd.DataFrame, sector_name: str):
    if 'Sector_Breadth' not in df_sector.columns:
        return
    breadth_series = df_sector['Sector_Breadth'].dropna()
    if breadth_series.empty:
        return

    latest_b = float(breadth_series.iloc[-1])
    st.markdown("---")
    st.subheader(f"📐 {sector_name} 板塊寬度 (Sector Breadth)")

    col_m, col_c = st.columns([1, 5])
    with col_m:
        b_delta = "⚠️ 超買過熱" if latest_b >= 80 else ("🔍 超賣注意" if latest_b <= 20 else "✅ 水位健康")
        b_color = "inverse" if latest_b >= 80 else "normal"
        st.metric("成分股 > MA20", f"{latest_b:.1f}%", delta=b_delta, delta_color=b_color)

    with col_c:
        fig_b = go.Figure()
        fig_b.add_trace(go.Scatter(
            x=df_sector.index, y=df_sector['Sector_Breadth'],
            line=dict(color='#a78bfa', width=2),
            fill='tozeroy', fillcolor='rgba(167,139,250,0.10)',
            hovertemplate="%{x|%Y-%m-%d}<br>%{y:.1f}% 成分股 > MA20<extra></extra>",
            connectgaps=False, showlegend=False,
        ))
        for y_val, color, label in [(80,"#ef4444","超買 80%"),(50,"rgba(255,255,255,0.25)","中軸 50%"),(20,"#22c55e","超賣 20%")]:
            fig_b.add_hline(y=y_val, line_dash="dash", line_color=color,
                            annotation_text=label, annotation_position="bottom right",
                            annotation_font=dict(color=color, size=10))
        fig_b.update_layout(
            template="plotly_dark", height=250,
            margin=dict(l=0, r=0, t=10, b=0),
            yaxis=dict(range=[0,100], title="成分股 > MA20 (%)"),
            plot_bgcolor="rgba(22,27,34,0.95)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_b, use_container_width=True)


# ── 機構吃貨走勢圖 (Up/Down Dollar Volume Ratio) ─────────────────────────────
def render_institutional_flow_chart(df_sector: pd.DataFrame, sector_name: str):
    """
    渲染板塊機構吃貨走勢圖。
    UD_DV_Ratio > 1 = 上漲日資金 > 下跌日資金 → 機構建倉
    UD_DV_Ratio < 1 = 下跌日資金 > 上漲日資金 → 機構派發
    """
    if 'UD_DV_Ratio' not in df_sector.columns:
        return

    ud = df_sector['UD_DV_Ratio'].dropna()
    if ud.empty:
        return

    latest_ud  = float(ud.iloc[-1])
    ud_sma5    = ud.rolling(5).mean()   # 5日平滑線

    # 判斷狀態
    if latest_ud >= 1.5:
        signal, s_color, s_desc = "🐳 強力建倉", "#22c55e", "大戶正在積極吸籌，上漲日資金遠超下跌日"
    elif latest_ud >= 1.1:
        signal, s_color, s_desc = "📈 溫和建倉", "#86efac", "資金偏向買方，板塊有機構逢低承接跡象"
    elif latest_ud >= 0.9:
        signal, s_color, s_desc = "⚖️ 多空平衡", "#9ca3af", "買賣方力道接近，方向不明，等待突破"
    elif latest_ud >= 0.7:
        signal, s_color, s_desc = "📉 溫和派發", "#fca5a5", "下跌日資金略多，注意是否有獲利了結壓力"
    else:
        signal, s_color, s_desc = "🚨 強力派發", "#ef4444", "下跌日資金遠超上漲日，機構可能正在出貨"

    st.markdown("---")
    st.subheader(f"🐳 {sector_name} 機構資金流向 (Up/Down Dollar Volume Ratio)")

    col_m, col_c = st.columns([1, 5])

    with col_m:
        st.metric("機構吃貨強度", f"{latest_ud:.2f}x",
                  delta=signal, delta_color="normal" if latest_ud >= 1.0 else "inverse")
        st.caption(s_desc)
        st.markdown(f"""
<div style='margin-top:12px;padding:8px;border-radius:6px;border-left:3px solid {s_color};
background:rgba(0,0,0,0.2);font-size:0.8rem;color:#9ca3af;'>
📌 <b>讀法：</b><br>
> 1.5x = 機構建倉<br>
1.0–1.5x = 偏多<br>
0.9–1.0x = 中性<br>
&lt; 0.9x = 派發出貨
</div>""", unsafe_allow_html=True)

    with col_c:
        fig_ud = go.Figure()

        # 建倉區（ratio > 1）填綠色
        fig_ud.add_trace(go.Scatter(
            x=ud.index, y=ud.clip(lower=1.0),
            fill='tozeroy', fillcolor='rgba(34,197,94,0.12)',
            line=dict(color='rgba(0,0,0,0)'), showlegend=False, hoverinfo='skip',
        ))
        # 派發區（ratio < 1）填紅色
        fig_ud.add_trace(go.Scatter(
            x=ud.index, y=ud.clip(upper=1.0),
            fill='tozeroy', fillcolor='rgba(239,68,68,0.10)',
            line=dict(color='rgba(0,0,0,0)'), showlegend=False, hoverinfo='skip',
        ))
        # 主線（原始）
        fig_ud.add_trace(go.Scatter(
            x=ud.index, y=ud,
            line=dict(color='#a78bfa', width=1.5),
            name="Up/Down DV Ratio",
            hovertemplate="%{x|%Y-%m-%d}<br>UD比值: %{y:.2f}x<extra></extra>",
        ))
        # 5日平滑線
        fig_ud.add_trace(go.Scatter(
            x=ud_sma5.index, y=ud_sma5,
            line=dict(color='#f59e0b', width=2, dash='dot'),
            name="5日均線",
            hovertemplate="%{x|%Y-%m-%d}<br>5MA: %{y:.2f}x<extra></extra>",
        ))
        # 基準線 1.0
        fig_ud.add_hline(y=1.0, line_dash="solid", line_color="rgba(255,255,255,0.3)",
                         annotation_text="中性基準 1.0x",
                         annotation_position="bottom right",
                         annotation_font=dict(color="rgba(255,255,255,0.5)", size=10))
        fig_ud.add_hline(y=1.5, line_dash="dash", line_color="rgba(34,197,94,0.4)",
                         annotation_text="強力建倉 1.5x",
                         annotation_position="top right",
                         annotation_font=dict(color="#22c55e", size=10))

        fig_ud.update_layout(
            template="plotly_dark",
            height=280,
            margin=dict(l=0, r=0, t=10, b=0),
            yaxis=dict(title="Up/Down DV Ratio", showgrid=True, gridcolor="#30363d"),
            xaxis=dict(showgrid=True, gridcolor="#30363d"),
            plot_bgcolor="rgba(22,27,34,0.95)",
            paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0),
        )
        st.plotly_chart(fig_ud, use_container_width=True)


# ── M5/M10/M20 動能三線交叉視覺化 ────────────────────────────────────────────
def render_momentum_crossover_chart(df_sector: pd.DataFrame, sector_name: str):
    """
    渲染 M5/M10/M20 動能三線走勢圖，並標記黃金交叉（▲）與死亡交叉（▽）。
    黃金交叉：M10 由下往上穿越 M20 → 波段動能確立，進場訊號
    死亡交叉：M10 由上往下穿越 M20 → 波段動能衰減，注意減倉
    """
    needed = ['M5', 'M10', 'M20']
    if not all(c in df_sector.columns for c in needed):
        return

    df_m = df_sector[needed].dropna()
    if len(df_m) < 20:
        return

    st.markdown("---")
    st.subheader(f"📊 {sector_name} 動能三線交叉圖 (M5 / M10 / M20)")
    st.caption("黃金交叉 🔺 = M10 上穿 M20（波段動能確立）｜死亡交叉 🔻 = M10 下穿 M20（動能衰減）")

    # 找出 M10 穿越 M20 的交叉點
    m10_series = df_m['M10']
    m20 = df_m['M20']
    prev_diff = (m10_series - m20).shift(1)
    curr_diff = (m10_series - m20)

    golden_cross = df_m.index[(prev_diff < 0) & (curr_diff >= 0)]  # M10 上穿 M20
    death_cross  = df_m.index[(prev_diff > 0) & (curr_diff <= 0)]  # M10 下穿 M20

    # 最新訊號
    latest_m5  = float(df_m['M5'].iloc[-1])
    latest_m10 = float(m10_series.iloc[-1])
    latest_m20 = float(m20.iloc[-1])

    col_m, col_c = st.columns([1, 5])
    with col_m:
        if latest_m10 > 0 and latest_m10 > latest_m20:
            st.metric("動能狀態", f"M10 {latest_m10:+.1f}%", delta="🔺 波段轉強", delta_color="normal")
        elif latest_m10 < 0 and latest_m10 < latest_m20:
            st.metric("動能狀態", f"M10 {latest_m10:+.1f}%", delta="🔻 波段衰減", delta_color="inverse")
        else:
            st.metric("動能狀態", f"M10 {latest_m10:+.1f}%", delta="⚖️ 多空拉鋸", delta_color="off")
        st.caption(f"M5: {latest_m5:+.1f}%\nM20: {latest_m20:+.1f}%")

    with col_c:
        fig_mom = go.Figure()

        # 零軸填色
        fig_mom.add_hrect(y0=0, y1=200,  fillcolor="rgba(34,197,94,0.04)",  line_width=0)
        fig_mom.add_hrect(y0=-200, y1=0, fillcolor="rgba(239,68,68,0.04)",  line_width=0)

        # 三條動能線
        for col_name, color, width, dash in [
            ('M20', '#6b7280', 1.5, 'dot'),
            ('M10', '#f59e0b', 1.8, 'dash'),
            ('M5',  '#60a5fa', 2.2, 'solid'),
        ]:
            fig_mom.add_trace(go.Scatter(
                x=df_m.index, y=df_m[col_name],
                name=col_name,
                line=dict(color=color, width=width, dash=dash),
                hovertemplate=f"%{{x|%Y-%m-%d}}<br>{col_name}: %{{y:.2f}}%<extra></extra>",
            ))

        # 黃金交叉標記（▲）
        if len(golden_cross) > 0:
            gc_y = [float(m10_series.loc[d]) for d in golden_cross if d in m10_series.index]
            fig_mom.add_trace(go.Scatter(
                x=list(golden_cross), y=gc_y,
                mode="markers",
                marker=dict(symbol="triangle-up", size=14,
                            color="#22c55e", line=dict(color='white', width=1)),
                name="黃金交叉 🔺",
                hovertemplate="🔺 黃金交叉<br>%{x|%Y-%m-%d}<br>M10: %{y:.2f}%<extra></extra>",
            ))

        # 死亡交叉標記（▽）
        if len(death_cross) > 0:
            dc_y = [float(m10_series.loc[d]) for d in death_cross if d in m10_series.index]
            fig_mom.add_trace(go.Scatter(
                x=list(death_cross), y=dc_y,
                mode="markers",
                marker=dict(symbol="triangle-down", size=14,
                            color="#ef4444", line=dict(color='white', width=1)),
                name="死亡交叉 🔻",
                hovertemplate="🔻 死亡交叉<br>%{x|%Y-%m-%d}<br>M10: %{y:.2f}%<extra></extra>",
            ))

        fig_mom.add_hline(y=0, line_dash="solid", line_color="rgba(255,255,255,0.2)")
        fig_mom.update_layout(
            template="plotly_dark",
            height=300,
            margin=dict(l=0, r=0, t=10, b=0),
            yaxis=dict(title="動能 (%)", showgrid=True, gridcolor="#30363d", zeroline=False),
            xaxis=dict(showgrid=True, gridcolor="#30363d"),
            plot_bgcolor="rgba(22,27,34,0.95)",
            paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0),
        )
        st.plotly_chart(fig_mom, use_container_width=True)

