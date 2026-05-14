import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
import plotly.graph_objects as go
import urllib3
import io
import os
import tempfile

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── WMO weather code → (label, emoji) ──────────────────────────────────────
WMO_CODES = {
    0: ("晴天", "☀️"), 1: ("大致晴朗", "🌤️"), 2: ("局部多雲", "⛅"),
    3: ("陰天", "☁️"), 45: ("霧", "🌫️"), 48: ("濃霧", "🌫️"),
    51: ("毛毛雨", "🌦️"), 53: ("毛毛雨", "🌦️"), 55: ("濃毛毛雨", "🌧️"),
    61: ("小雨", "🌧️"), 63: ("中雨", "🌧️"), 65: ("大雨", "🌧️"),
    71: ("小雪", "🌨️"), 73: ("中雪", "🌨️"), 75: ("大雪", "❄️"),
    77: ("冰晶", "❄️"), 80: ("陣雨", "🌦️"), 81: ("中陣雨", "🌧️"),
    82: ("強陣雨", "⛈️"), 85: ("陣雪", "🌨️"), 86: ("強陣雪", "❄️"),
    95: ("雷陣雨", "⛈️"), 96: ("雷陣雨夾冰雹", "⛈️"), 99: ("強雷雨", "🌩️"),
}

def wmo_label(code):
    return WMO_CODES.get(int(code), ("未知", "🌡️"))

# ── PDF 報表產生器 ────────────────────────────────────────────────────────────
def generate_pdf(df, location_str, today, t_label):
    from fpdf import FPDF

    # Windows 系統中文字型（Microsoft JhengHei）
    FONT_PATH = "C:/Windows/Fonts/msjh.ttc"
    if not os.path.exists(FONT_PATH):
        FONT_PATH = "C:/Windows/Fonts/simsun.ttc"   # 備用：新細明體

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.add_font("zh", fname=FONT_PATH, uni=True)

    # ── 標題列 ──
    pdf.set_fill_color(26, 127, 212)
    pdf.rect(0, 0, 210, 30, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("zh", size=20)
    pdf.set_xy(0, 7)
    pdf.cell(210, 12, "  智能天氣預測報告", align="C")
    pdf.set_font("zh", size=10)
    pdf.set_xy(0, 20)
    pdf.cell(210, 8, f"產生時間：{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}", align="C")

    pdf.set_text_color(40, 40, 40)
    pdf.ln(18)

    # ── 地點 ──
    pdf.set_font("zh", size=12)
    pdf.set_fill_color(220, 237, 255)
    pdf.cell(0, 9, f"  📍 地點：{location_str}", ln=True, fill=True)
    pdf.ln(3)

    # ── 今日摘要 ──
    pdf.set_font("zh", size=13)
    pdf.set_fill_color(26, 127, 212)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 9, f"  今日天氣摘要（{today['日期']}）", ln=True, fill=True)
    pdf.set_text_color(40, 40, 40)
    pdf.set_font("zh", size=11)
    pdf.ln(2)

    rows_today = [
        ("天氣狀況", t_label),
        ("最高溫 / 最低溫", f"{today['最高溫']}°C  /  {today['最低溫']}°C"),
        ("降水量", f"{today['降水量']} mm"),
        ("最大風速", f"{today['最大風速']} km/h"),
        ("UV 指數", str(today["UV指數"])),
    ]
    for label, val in rows_today:
        pdf.set_fill_color(245, 250, 255)
        pdf.cell(55, 8, f"  {label}", border=1, fill=True)
        pdf.cell(0, 8, f"  {val}", border=1, ln=True)
    pdf.ln(5)

    # ── 氣溫趨勢圖 ──
    try:
        fig_tmp = go.Figure()
        fig_tmp.add_trace(go.Scatter(
            x=df["日期"], y=df["最高溫"], name="最高溫",
            line=dict(color="#e53935", width=3), mode="lines+markers"))
        fig_tmp.add_trace(go.Scatter(
            x=df["日期"], y=df["最低溫"], name="最低溫",
            line=dict(color="#1e88e5", width=3), mode="lines+markers"))
        fig_tmp.update_layout(
            paper_bgcolor="white", plot_bgcolor="white",
            font=dict(color="#333", size=12),
            width=680, height=260,
            margin=dict(l=45, r=20, t=20, b=45),
            legend=dict(bgcolor="white"),
        )
        img_bytes = fig_tmp.to_image(format="png")
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(img_bytes)
            tmp_path = tmp.name

        pdf.set_font("zh", size=13)
        pdf.set_fill_color(26, 127, 212)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 9, "  氣溫趨勢圖", ln=True, fill=True)
        pdf.set_text_color(40, 40, 40)
        pdf.ln(2)
        pdf.image(tmp_path, x=10, w=185)
        os.unlink(tmp_path)
        pdf.ln(4)
    except Exception:
        pass  # kaleido 未安裝時略過圖表

    # ── 7天預報表格 ──
    pdf.set_font("zh", size=13)
    pdf.set_fill_color(26, 127, 212)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 9, "  未來 7 天天氣預報", ln=True, fill=True)
    pdf.set_text_color(40, 40, 40)
    pdf.ln(2)

    headers = ["日期",  "天氣狀況", "最高(°C)", "最低(°C)", "降水(mm)", "風速(km/h)", "UV"]
    widths  = [27,      38,          24,          24,          24,          28,           18]

    pdf.set_font("zh", size=10)
    pdf.set_fill_color(26, 127, 212)
    pdf.set_text_color(255, 255, 255)
    for h, w in zip(headers, widths):
        pdf.cell(w, 8, h, border=1, align="C", fill=True)
    pdf.ln()

    pdf.set_text_color(40, 40, 40)
    for i, (_, row) in enumerate(df.head(7).iterrows()):
        label, _ = wmo_label(row["天氣代碼"])
        vals = [
            row["日期"][5:],
            label,
            f"{row['最高溫']:.1f}",
            f"{row['最低溫']:.1f}",
            f"{row['降水量']:.1f}",
            f"{row['最大風速']:.0f}",
            f"{row['UV指數']:.0f}",
        ]
        fill_color = (240, 248, 255) if i % 2 == 0 else (255, 255, 255)
        pdf.set_fill_color(*fill_color)
        for v, w in zip(vals, widths):
            pdf.cell(w, 7, v, border=1, align="C", fill=True)
        pdf.ln()

    # ── 頁尾 ──
    pdf.set_y(-15)
    pdf.set_font("zh", size=8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 8, "資料來源：Open-Meteo API  |  智能天氣預測儀表板", align="C")

    return bytes(pdf.output())

@st.cache_data(ttl=300, show_spinner=False)
def reverse_geocode(lat, lon):
    """用 OpenStreetMap Nominatim 取得縣市鄉鎮中文名稱"""
    try:
        url = (
            f"https://nominatim.openstreetmap.org/reverse"
            f"?lat={lat}&lon={lon}&format=json&accept-language=zh-TW"
        )
        r = requests.get(url, verify=False, timeout=8,
                         headers={"User-Agent": "WeatherApp/1.0"})
        if r.status_code == 200:
            addr = r.json().get("address", {})
            # 縣市：city > county > state
            city = addr.get("city") or addr.get("county") or addr.get("state", "")
            # 鄉鎮區：suburb > town > village > district
            town = (addr.get("suburb") or addr.get("town")
                    or addr.get("village") or addr.get("district", ""))
            country = addr.get("country", "")
            return city, town, country
    except Exception:
        pass
    return "", "", ""

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="智能天氣預測儀表板", page_icon="🌤️", layout="wide")

st.markdown("""
<style>
/* ── 全域背景漸層 ── */
[data-testid="stAppViewContainer"] {
    background: linear-gradient(180deg, #0c3d6e 0%, #1a7fd4 45%, #64b5f6 100%);
    color: #e0e0e0;
}
[data-testid="stHeader"] { background: transparent; }

/* ── 玻璃卡片 ── */
.glass-card {
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 16px;
    padding: 18px 14px;
    text-align: center;
    backdrop-filter: blur(10px);
    transition: transform .2s, box-shadow .2s;
    margin-bottom: 8px;
}
.glass-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 32px rgba(0,168,255,0.25);
}
.card-date   { font-size: 0.78rem; color: #aac4ff; font-weight: 600; letter-spacing: 1px; }
.card-icon   { font-size: 2.2rem; margin: 4px 0; }
.card-label  { font-size: 0.7rem; color: #c0cfe8; margin-bottom: 6px; }
.card-hi     { font-size: 1.4rem; font-weight: 700; color: #ff7043; }
.card-lo     { font-size: 1.1rem; font-weight: 600; color: #64b5f6; }
.card-rain   { font-size: 0.78rem; color: #90caf9; margin-top: 6px; }
.card-wind   { font-size: 0.72rem; color: #b0bec5; }

/* ── 今日大橫幅 ── */
.today-banner {
    background: linear-gradient(90deg, rgba(0,168,255,0.25), rgba(120,80,255,0.25));
    border: 1px solid rgba(0,168,255,0.3);
    border-radius: 20px;
    padding: 24px 32px;
    margin-bottom: 20px;
    backdrop-filter: blur(12px);
}
.today-banner h1 { font-size: 3rem; margin: 0; }
.today-banner .sub { font-size: 1rem; color: #aac4ff; }

/* ── Metric 覆寫 ── */
[data-testid="stMetric"] {
    background: rgba(255,255,255,0.07);
    border-radius: 12px;
    padding: 12px;
    border: 1px solid rgba(255,255,255,0.1);
}
[data-testid="stMetricLabel"]  { color: #aac4ff !important; }
[data-testid="stMetricValue"]  { color: #ffffff !important; }

/* ── Tab 樣式 ── */
[data-testid="stTabs"] button { color: #aac4ff !important; }
[data-testid="stTabs"] button[aria-selected="true"] {
    border-bottom: 2px solid #00a8ff !important;
    color: #ffffff !important;
}

/* ── 分隔線 ── */
hr { border-color: rgba(255,255,255,0.1) !important; }

/* ── Sidebar & input ── */
[data-testid="stSidebar"] { background: rgba(12,61,110,0.92); }
input[type="number"] {
  background: rgba(255,255,255,0.92) !important;
  color: #1a3a5c !important;
  font-size: 16px !important;
  font-weight: 600 !important;
  border: 2px solid rgba(255,255,255,0.6) !important;
  border-radius: 8px !important;
}
input[type="number"]::placeholder {
  color: rgba(26,58,92,0.5) !important;
}
[data-testid="stNumberInput"] label {
  color: #ffffff !important;
  font-size: 14px !important;
  font-weight: 600 !important;
  text-shadow: 0 1px 3px rgba(0,0,0,0.5) !important;
}
</style>
""", unsafe_allow_html=True)

# ── 彩虹滑鼠軌跡（用 components.html + window.parent 才能執行 JS）────────────
components.html("""
<script>
(function() {
    const pd = window.parent.document;
    if (!pd.getElementById('rainbow-trail-style')) {
        const s = pd.createElement('style');
        s.id = 'rainbow-trail-style';
        s.textContent = `
            .rainbow-dot {
                position: fixed;
                border-radius: 50%;
                pointer-events: none;
                z-index: 99999;
                transform: translate(-50%, -50%);
                animation: rainbow-fade 0.8s ease-out forwards;
            }
            @keyframes rainbow-fade {
                0%   { opacity:1; transform:translate(-50%,-50%) scale(1); }
                100% { opacity:0; transform:translate(-50%,-50%) scale(0.1); }
            }
        `;
        pd.head.appendChild(s);
    }
    const COLORS = [
        '#ff0000','#ff4500','#ff7700','#ffaa00',
        '#ffdd00','#aaff00','#00ff44','#00ffcc',
        '#00ccff','#0088ff','#4400ff','#aa00ff','#ff00cc'
    ];
    let colorIdx = 0, lastX = 0, lastY = 0, ticking = false;
    function spawnDot(x, y) {
        const dot = pd.createElement('div');
        dot.className = 'rainbow-dot';
        const size = Math.random() * 10 + 6;
        const color = COLORS[colorIdx++ % COLORS.length];
        dot.style.cssText = [
            `left:${x}px`, `top:${y}px`,
            `width:${size}px`, `height:${size}px`,
            `background:${color}`,
            `box-shadow:0 0 ${size * 1.5}px ${color}`
        ].join(';');
        pd.body.appendChild(dot);
        setTimeout(() => dot.remove(), 850);
    }
    pd.addEventListener('mousemove', function(e) {
        const dx = e.clientX - lastX, dy = e.clientY - lastY;
        if (dx*dx + dy*dy < 25) return;
        lastX = e.clientX; lastY = e.clientY;
        if (!ticking) {
            ticking = true;
            window.parent.requestAnimationFrame(function() {
                spawnDot(lastX, lastY);
                ticking = false;
            });
        }
    });
})();
</script>
""", height=0)

# ── Header ──────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center; padding: 10px 0 4px 0;">
  <span style="font-size:2.6rem; font-weight:800;
               background: linear-gradient(90deg,#00d2ff,#7b2ff7);
               -webkit-background-clip:text; -webkit-text-fill-color:transparent;">
    🌤️ 智能天氣預測儀表板
  </span><br>
  <span style="color:#aac4ff; font-size:0.95rem;">輸入座標或一鍵定位，輕鬆掌握未來一週天氣動態</span>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ── Session state ────────────────────────────────────────────────────────────
for k, v in [('lat', 24.7326), ('lon', 121.0918)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── 接收瀏覽器 GPS 座標（navigator.geolocation 回傳後以 query param 帶入）──────
if 'geo_lat' in st.query_params:
    try:
        st.session_state['lat'] = float(st.query_params['geo_lat'])
        st.session_state['lon'] = float(st.query_params['geo_lon'])
        _city, _town, _country = reverse_geocode(
            st.session_state['lat'], st.session_state['lon']
        )
        _loc = " ".join(filter(None, [_country, _city, _town])) or \
               f"{st.session_state['lat']:.4f}, {st.session_state['lon']:.4f}"
        st.toast(f"✅ GPS 定位成功！{_loc}", icon="📍")
        st.balloons()
    except Exception:
        st.error("GPS 座標讀取失敗，請手動輸入。")
    st.query_params.clear()

# ── 定位 + 輸入 ──────────────────────────────────────────────────────────────
col_btn, col_lat, col_lon = st.columns([1, 1, 1])

with col_btn:
    # 使用瀏覽器原生 GPS（比 IP 定位精準許多）
    components.html("""
    <style>
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: sans-serif; }
    #gps-btn {
        display: block; width: 100%; margin-top: 32px;
        padding: 9px 12px; border: none; border-radius: 8px; cursor: pointer;
        background: #1a7fd4; color: white; font-size: 14px; font-weight: 600;
        transition: background .2s;
    }
    #gps-btn:hover:not(:disabled) { background: #1260a8; }
    #gps-btn:disabled { background: #555; cursor: not-allowed; }
    #gps-msg { margin-top: 6px; font-size: 11px; color: #90caf9; min-height: 16px; }
    </style>
    <button id="gps-btn" onclick="doGPS()">📍 GPS 精準定位</button>
    <div id="gps-msg"></div>
    <script>
    function doGPS() {
        const btn = document.getElementById('gps-btn');
        const msg = document.getElementById('gps-msg');

        // 透過 window.parent.navigator 使用父頁面的 Geolocation，
        // 繞過 iframe 沒有 allow="geolocation" 的限制
        const geo = window.parent.navigator.geolocation;

        if (!geo) {
            msg.style.color = '#ff8a80';
            msg.textContent = '⚠️ 瀏覽器不支援定位，請手動輸入座標';
            return;
        }

        btn.textContent = '⏳ 定位中…';
        btn.disabled = true;
        msg.style.color = '#90caf9';
        msg.textContent = '請在瀏覽器彈窗中允許位置存取…';

        geo.getCurrentPosition(
            function(pos) {
                const url = new URL(window.parent.location.href);
                url.searchParams.set('geo_lat', pos.coords.latitude.toFixed(6));
                url.searchParams.set('geo_lon', pos.coords.longitude.toFixed(6));
                window.parent.location.href = url.toString();
            },
            function(err) {
                btn.textContent = '📍 GPS 精準定位';
                btn.disabled = false;
                msg.style.color = '#ff8a80';
                const msgs = {
                    1: '已拒絕位置存取，請在網址列允許定位',
                    2: '無法取得位置訊號',
                    3: '定位逾時，請再試一次'
                };
                msg.textContent = '❌ ' + (msgs[err.code] || '定位失敗，請手動輸入座標');
            },
            { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 }
        );
    }
    </script>
    """, height=85)

with col_lat:
    lat = st.number_input("緯度 Latitude", value=st.session_state['lat'], format="%.4f")
with col_lon:
    lon = st.number_input("經度 Longitude", value=st.session_state['lon'], format="%.4f")

st.markdown("---")

# ── 主查詢按鈕 ───────────────────────────────────────────────────────────────
if st.button("🚀 產生天氣預測報告", type="primary", use_container_width=True):
    api_url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=weathercode,temperature_2m_max,temperature_2m_min,"
        f"precipitation_sum,windspeed_10m_max,uv_index_max"
        f"&timezone=auto"
    )

    with st.spinner("🛰️ 正在從氣象模型拉取資料..."):
        try:
            resp = requests.get(api_url, verify=False, timeout=10)
            resp.raise_for_status()
            daily = resp.json().get("daily", {})

            # ── 反向地理編碼取得縣市鄉鎮 ──────────────────────────────────
            city, town, country = reverse_geocode(lat, lon)
            location_str = " ".join(filter(None, [country, city, town])) or f"{lat:.4f}, {lon:.4f}"

            df = pd.DataFrame({
                "日期":       daily["time"],
                "天氣代碼":   daily["weathercode"],
                "最高溫":     daily["temperature_2m_max"],
                "最低溫":     daily["temperature_2m_min"],
                "降水量":     daily["precipitation_sum"],
                "最大風速":   daily["windspeed_10m_max"],
                "UV指數":     daily["uv_index_max"],
            })

            # ── 今日大橫幅 ──────────────────────────────────────────────────
            today = df.iloc[0]
            t_label, t_icon = wmo_label(today["天氣代碼"])
            avg_today = (today["最高溫"] + today["最低溫"]) / 2

            # 存入 session_state 供 PDF 與動畫使用
            st.session_state['_wd'] = {
                'df': df, 'location_str': location_str,
                'today': today.to_dict(), 't_label': t_label,
                'weather_code': int(today["天氣代碼"]),
                'wind_speed':   float(today["最大風速"]),
            }

            st.markdown(f"""
            <div class="today-banner">
              <table style="width:100%; border:none;">
                <tr>
                  <td style="width:60%; vertical-align:middle;">
                    <div style="font-size:1.15rem; font-weight:700; color:#ffffff; margin-bottom:2px;">
                      📍 {location_str}
                    </div>
                    <div style="font-size:1rem; color:#aac4ff;">📅 今日 {today['日期']}</div>
                    <div style="font-size:4rem; margin:4px 0;">{t_icon}</div>
                    <div style="font-size:1.6rem; font-weight:700;">{t_label}</div>
                    <div style="font-size:0.9rem; color:#aac4ff; margin-top:4px;">
                      🌡️ {today['最低溫']}°C ~ {today['最高溫']}°C &nbsp;|&nbsp;
                      💧 {today['降水量']} mm &nbsp;|&nbsp;
                      💨 {today['最大風速']} km/h &nbsp;|&nbsp;
                      ☀️ UV {today['UV指數']}
                    </div>
                  </td>
                  <td style="text-align:right; vertical-align:middle;">
                    <div style="font-size:5rem; font-weight:900;
                                background:linear-gradient(180deg,#ff7043,#ffd740);
                                -webkit-background-clip:text; -webkit-text-fill-color:transparent;">
                      {avg_today:.0f}°
                    </div>
                    <div style="color:#aac4ff; font-size:0.9rem;">平均氣溫</div>
                  </td>
                </tr>
              </table>
            </div>
            """, unsafe_allow_html=True)

            # ── 老闆快問快答 ──────────────────────────────────────────────
            next7 = df.iloc[1:8].copy()   # 排除今天，取後續7天
            next7["溫差"] = next7["最高溫"] - next7["最低溫"]
            boss_max_diff_row = next7.loc[next7["溫差"].idxmax()]
            boss_avg_hi = next7["最高溫"].mean()

            st.markdown(f"""
            <div style="background:linear-gradient(90deg,rgba(255,193,7,0.15),rgba(255,87,34,0.15));
                        border:1px solid rgba(255,193,7,0.4); border-radius:16px;
                        padding:20px 28px; margin-bottom:16px;">
              <div style="font-size:1rem; font-weight:700; color:#ffd740; margin-bottom:12px;">
                🤵 老闆問答 — 未來7天摘要
              </div>
              <table style="width:100%; border:none; border-collapse:separate; border-spacing:0 6px;">
                <tr>
                  <td style="color:#aac4ff; width:52%;">📊 日夜溫差最大的一天</td>
                  <td style="color:#ffffff; font-weight:700; font-size:1.1rem;">
                    {boss_max_diff_row['日期']} &nbsp;
                    <span style="color:#ff7043;">（溫差 {boss_max_diff_row['溫差']:.1f}°C，
                    {boss_max_diff_row['最高溫']}° ↔ {boss_max_diff_row['最低溫']}°）</span>
                  </td>
                </tr>
                <tr>
                  <td style="color:#aac4ff;">🌡️ 未來7天平均最高溫</td>
                  <td style="color:#ffd740; font-weight:700; font-size:1.1rem;">
                    {boss_avg_hi:.1f}°C
                  </td>
                </tr>
              </table>
            </div>
            """, unsafe_allow_html=True)

            # ── 頂部摘要 Metrics ──────────────────────────────────────────
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🌡️ 今日最高溫", f"{today['最高溫']}°C")
            c2.metric("❄️ 今日最低溫", f"{today['最低溫']}°C")
            c3.metric("💨 最大風速",   f"{today['最大風速']} km/h")
            c4.metric("☀️ UV 指數",    f"{today['UV指數']}")

            st.markdown("---")

            # ── Tabs ─────────────────────────────────────────────────────
            tab1, tab2, tab3, tab4 = st.tabs([
                "🗓️ 7天預報看板", "📈 氣溫趨勢", "🌧️ 降水 & 風速", "📋 原始數據"
            ])

            # ─── Tab 1: 7天卡片 ───────────────────────────────────────────
            with tab1:
                st.markdown("#### 未來一週天氣預覽")
                cols = st.columns(7)
                for i in range(min(7, len(df))):
                    row = df.iloc[i]
                    label, icon = wmo_label(row["天氣代碼"])
                    rain = row["降水量"]
                    rain_str = f"☔ {rain} mm" if rain > 0 else "☀️ 無雨"
                    with cols[i]:
                        st.markdown(f"""
                        <div class="glass-card">
                          <div class="card-date">{row['日期'][5:]}</div>
                          <div class="card-icon">{icon}</div>
                          <div class="card-label">{label}</div>
                          <div class="card-hi">{row['最高溫']}°C</div>
                          <div class="card-lo">{row['最低溫']}°C</div>
                          <div class="card-rain">{rain_str}</div>
                          <div class="card-wind">💨 {row['最大風速']} km/h</div>
                        </div>
                        """, unsafe_allow_html=True)

            # ─── Tab 2: 氣溫趨勢 Plotly ──────────────────────────────────
            with tab2:
                st.markdown("#### 最高溫 / 最低溫 趨勢")
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df["日期"], y=df["最高溫"],
                    name="最高溫", mode="lines+markers",
                    line=dict(color="#ff7043", width=3),
                    marker=dict(size=8, symbol="circle"),
                    fill="tozeroy", fillcolor="rgba(255,112,67,0.12)"
                ))
                fig.add_trace(go.Scatter(
                    x=df["日期"], y=df["最低溫"],
                    name="最低溫", mode="lines+markers",
                    line=dict(color="#64b5f6", width=3),
                    marker=dict(size=8, symbol="circle"),
                    fill="tozeroy", fillcolor="rgba(100,181,246,0.12)"
                ))
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#e0e0e0"),
                    legend=dict(bgcolor="rgba(0,0,0,0)"),
                    xaxis=dict(gridcolor="rgba(255,255,255,0.08)", showline=False),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.08)", title="°C"),
                    hovermode="x unified",
                    margin=dict(l=40, r=20, t=20, b=40),
                )
                st.plotly_chart(fig, use_container_width=True)

                # UV 橫條圖
                st.markdown("#### UV 指數")
                fig2 = go.Figure(go.Bar(
                    x=df["日期"], y=df["UV指數"],
                    marker=dict(
                        color=df["UV指數"],
                        colorscale=[[0,"#64b5f6"],[0.5,"#ffd740"],[1,"#ff1744"]],
                        showscale=True,
                        colorbar=dict(title="UV", tickfont=dict(color="#e0e0e0")),
                    ),
                ))
                fig2.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#e0e0e0"),
                    xaxis=dict(gridcolor="rgba(255,255,255,0.08)"),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.08)"),
                    margin=dict(l=40, r=20, t=10, b=40),
                )
                st.plotly_chart(fig2, use_container_width=True)

            # ─── Tab 3: 降水 & 風速 ───────────────────────────────────────
            with tab3:
                st.markdown("#### 每日降水量 (mm)")
                fig3 = go.Figure(go.Bar(
                    x=df["日期"], y=df["降水量"],
                    marker=dict(
                        color=df["降水量"],
                        colorscale=[[0,"#0d47a1"],[1,"#00e5ff"]],
                        showscale=True,
                        colorbar=dict(title="mm", tickfont=dict(color="#e0e0e0")),
                    ),
                    text=df["降水量"].apply(lambda v: f"{v} mm"),
                    textposition="outside", textfont=dict(color="#e0e0e0"),
                ))
                fig3.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#e0e0e0"),
                    xaxis=dict(gridcolor="rgba(255,255,255,0.08)"),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.08)", title="mm"),
                    margin=dict(l=40, r=20, t=10, b=40),
                )
                st.plotly_chart(fig3, use_container_width=True)

                st.markdown("#### 最大風速 (km/h)")
                fig4 = go.Figure(go.Scatter(
                    x=df["日期"], y=df["最大風速"],
                    mode="lines+markers",
                    line=dict(color="#b2ff59", width=3),
                    marker=dict(size=9),
                    fill="tozeroy", fillcolor="rgba(178,255,89,0.1)",
                ))
                fig4.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#e0e0e0"),
                    xaxis=dict(gridcolor="rgba(255,255,255,0.08)"),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.08)", title="km/h"),
                    margin=dict(l=40, r=20, t=10, b=40),
                )
                st.plotly_chart(fig4, use_container_width=True)

            # ─── Tab 4: 原始數據 ──────────────────────────────────────────
            with tab4:
                display_df = df.copy()
                display_df["天氣狀況"] = display_df["天氣代碼"].apply(
                    lambda c: f"{wmo_label(c)[1]} {wmo_label(c)[0]}"
                )
                display_df = display_df[["日期","天氣狀況","最高溫","最低溫","降水量","最大風速","UV指數"]]
                display_df.columns = ["日期","天氣狀況","最高溫(°C)","最低溫(°C)","降水量(mm)","最大風速(km/h)","UV指數"]
                st.dataframe(
                    display_df, use_container_width=True, hide_index=True,
                    column_config={
                        "最高溫(°C)":   st.column_config.NumberColumn(format="%.1f °C"),
                        "最低溫(°C)":   st.column_config.NumberColumn(format="%.1f °C"),
                        "降水量(mm)":   st.column_config.ProgressColumn(min_value=0, max_value=50, format="%.1f mm"),
                        "最大風速(km/h)": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f km/h"),
                        "UV指數":       st.column_config.NumberColumn(format="%.0f"),
                    }
                )

        except requests.exceptions.RequestException as e:
            st.error(f"❌ 連線 API 時發生錯誤：{e}")

# ── PDF 輸出區（放在主按鈕之外，session_state 存活於每次重繪）──────────────────
if '_wd' in st.session_state:
    st.markdown("---")
    st.markdown("#### 📄 輸出 PDF 報表")
    col_gen, col_dl = st.columns([1, 1])

    with col_gen:
        if st.button("🖨️ 產生 PDF", use_container_width=True):
            with st.spinner("正在產生 PDF，請稍候..."):
                try:
                    wd = st.session_state['_wd']
                    pdf_bytes = generate_pdf(
                        wd['df'], wd['location_str'], wd['today'], wd['t_label']
                    )
                    st.session_state['_pdf_bytes'] = pdf_bytes
                    st.session_state['_pdf_filename'] = (
                        f"天氣報告_{wd['location_str']}_{wd['today']['日期']}.pdf"
                        .replace(" ", "_")
                    )
                    st.success("✅ PDF 已產生，點右側按鈕下載")
                except Exception as e:
                    st.error(f"❌ PDF 產生失敗：{e}")

    with col_dl:
        if '_pdf_bytes' in st.session_state:
            st.download_button(
                label="⬇️ 下載 PDF",
                data=st.session_state['_pdf_bytes'],
                file_name=st.session_state['_pdf_filename'],
                mime="application/pdf",
                use_container_width=True,
            )

# ── 動態天氣背景動畫 ──────────────────────────────────────────────────────────
if '_wd' in st.session_state:
    _wx_code = st.session_state['_wd']['weather_code']
    _wx_wind = st.session_state['_wd']['wind_speed']
    _wx_init = f"<script>window.__WX={{code:{_wx_code},wind:{_wx_wind}}};</script>"
    _wx_anim = """<script>
(function() {
    const CODE = window.__WX.code;
    const WIND = window.__WX.wind;
    const pw  = window.parent;
    const doc = pw.document;

    // 清除前一次動畫
    ['_wx_layer','_wx_canvas','_wx_css'].forEach(id => {
        const e = doc.getElementById(id); if (e) e.remove();
    });
    if (pw._wxAnimId) pw.cancelAnimationFrame(pw._wxAnimId);

    // 天氣分類
    const isThunder   = [95,96,99].includes(CODE);
    const isHeavyRain = [80,81,82].includes(CODE) || isThunder;
    const isRain      = [51,53,55,61,63,65].includes(CODE) || isHeavyRain;
    const isSnow      = [71,73,75,77,85,86].includes(CODE);
    const isFog       = [45,48].includes(CODE);
    const isOvercast  = CODE === 3;
    const isPartCloud = CODE === 2;
    const isSunny     = CODE <= 1;
    const hasLeaves   = WIND >= 25 && !isRain && !isSnow;

    // CSS 注入上層頁面
    const css = doc.createElement('style');
    css.id = '_wx_css';
    css.textContent = `
        #_wx_layer{position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:1;overflow:hidden}
        @keyframes _sun_pulse{
            0%,100%{box-shadow:0 0 50px 20px rgba(255,220,0,.55),0 0 100px 40px rgba(255,160,0,.18)}
            50%    {box-shadow:0 0 80px 35px rgba(255,220,0,.75),0 0 160px 70px rgba(255,160,0,.28)}
        }
        @keyframes _ray_spin{to{transform:translate(-50%,-50%) rotate(360deg)}}
        @keyframes _cloud_go{from{transform:translateX(-450px)}to{transform:translateX(calc(100vw + 450px))}}
        ._wx_sun{position:absolute;top:-70px;right:-70px;width:220px;height:220px;border-radius:50%;
                 background:radial-gradient(circle at 38% 38%,#fffde7,#ffd600 55%,#ff8f00);
                 animation:_sun_pulse 2.8s ease-in-out infinite}
        ._wx_rays{position:absolute;top:40px;left:40px;width:140px;height:140px;
                  animation:_ray_spin 18s linear infinite;transform-origin:50% 50%}
        ._wx_ray{position:absolute;top:50%;left:50%;width:2px;height:160px;margin-top:-80px;
                 background:linear-gradient(transparent 15%,rgba(255,235,0,.5),transparent 85%);
                 transform-origin:50% 50%}
        ._wx_cloud{position:absolute;background:rgba(255,255,255,.82);border-radius:60px;
                   animation:_cloud_go linear infinite}
        ._wx_cloud::before,._wx_cloud::after{content:'';position:absolute;background:rgba(255,255,255,.82);border-radius:50%}
    `;
    doc.head.appendChild(css);

    // DOM 圖層（太陽 + 雲）
    const layer = doc.createElement('div');
    layer.id = '_wx_layer';
    doc.body.appendChild(layer);

    // 太陽
    if (isSunny || isPartCloud) {
        const sun = doc.createElement('div');
        sun.className = '_wx_sun';
        layer.appendChild(sun);
        const rDiv = doc.createElement('div');
        rDiv.className = '_wx_rays';
        for (let i = 0; i < 12; i++) {
            const r = doc.createElement('div');
            r.className = '_wx_ray';
            r.style.transform = `translateX(-50%) rotate(${i*30}deg)`;
            rDiv.appendChild(r);
        }
        layer.appendChild(rDiv);
    }

    // 雲
    if (isOvercast || isPartCloud || isFog) {
        const n = (isOvercast || isFog) ? 6 : 3;
        for (let i = 0; i < n; i++) {
            const w   = 120 + Math.random()*130;
            const top = Math.random()*50;
            const dur = 28 + Math.random()*28;
            const del = -(Math.random()*dur);
            const opa = isFog ? 0.18+Math.random()*0.12 : 0.5+Math.random()*0.4;
            const c = doc.createElement('div');
            c.className = '_wx_cloud';
            c.style.cssText = `width:${w*2}px;height:${w*0.4}px;top:${top}%;opacity:${opa};animation-duration:${dur}s;animation-delay:${del}s`;
            [{s:0.75,l:0.3},{s:0.55,l:0.95}].forEach(({s,l}) => {
                const b = doc.createElement('div');
                b.style.cssText = `width:${w*s}px;height:${w*s}px;top:-${w*s*0.44}px;left:${w*l}px;position:absolute;background:rgba(255,255,255,.82);border-radius:50%`;
                c.appendChild(b);
            });
            layer.appendChild(c);
        }
    }

    // Canvas（雨 / 雪 / 落葉 / 閃電）
    if (isRain || isSnow || hasLeaves || isThunder) {
        const cv = doc.createElement('canvas');
        cv.id = '_wx_canvas';
        cv.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:2';
        cv.width = pw.innerWidth; cv.height = pw.innerHeight;
        doc.body.appendChild(cv);
        const ctx = cv.getContext('2d');
        let W = cv.width, H = cv.height;
        pw.addEventListener('resize', () => { W = cv.width = pw.innerWidth; H = cv.height = pw.innerHeight; });

        const pts = [];
        if (isRain) {
            const cnt = isHeavyRain ? 400 : 150;
            for (let i = 0; i < cnt; i++)
                pts.push({type:'rain', x:Math.random()*W, y:Math.random()*H,
                          len:10+Math.random()*20, speed:(isHeavyRain?20:9)+Math.random()*8,
                          op:0.3+Math.random()*0.45});
        }
        if (isSnow) {
            for (let i = 0; i < 120; i++)
                pts.push({type:'snow', x:Math.random()*W, y:Math.random()*H,
                          r:2+Math.random()*4, speed:0.5+Math.random()*1.5,
                          drift:(Math.random()-0.5)*1.2, op:0.5+Math.random()*0.5});
        }
        if (hasLeaves) {
            const em = ['🍂','🍁','🍃'];
            for (let i = 0; i < 22; i++)
                pts.push({type:'leaf', x:Math.random()*W, y:Math.random()*H,
                          emoji:em[i%3], sz:14+Math.random()*14,
                          speed:2+Math.random()*2.5, drift:3+Math.random()*5,
                          rot:Math.random()*360, rotSpd:(Math.random()-0.5)*6});
        }

        let ltTimer = 0, ltFlash = false, ltAlpha = 0, ltBolt = [];
        function newBolt() {
            const bx = W*0.25 + Math.random()*W*0.5;
            const b = [{x:bx, y:0}]; let cy = 0;
            while (cy < H*0.75) {
                cy += 35 + Math.random()*55;
                b.push({x: b[b.length-1].x + (Math.random()-0.5)*100, y: cy});
            }
            return b;
        }

        function draw() {
            ctx.clearRect(0, 0, W, H);

            // 閃電
            if (isThunder) {
                ltTimer++;
                if (!ltFlash && ltTimer > 90 + Math.random()*150) {
                    ltFlash = true; ltAlpha = 1; ltBolt = newBolt(); ltTimer = 0;
                }
                if (ltFlash) {
                    ctx.fillStyle = `rgba(255,255,240,${ltAlpha*0.18})`;
                    ctx.fillRect(0, 0, W, H);
                    ctx.beginPath();
                    ctx.moveTo(ltBolt[0].x, ltBolt[0].y);
                    ltBolt.forEach((p, i) => { if (i > 0) ctx.lineTo(p.x, p.y); });
                    ctx.strokeStyle = `rgba(255,255,180,${ltAlpha})`;
                    ctx.lineWidth   = 3 + ltAlpha*2;
                    ctx.shadowColor = '#ffff80';
                    ctx.shadowBlur  = 30;
                    ctx.stroke();
                    ctx.shadowBlur = 0;
                    ltAlpha -= 0.06;
                    if (ltAlpha <= 0) ltFlash = false;
                }
            }

            // 粒子
            for (const p of pts) {
                if (p.type === 'rain') {
                    ctx.strokeStyle = `rgba(180,220,255,${p.op})`;
                    ctx.lineWidth = 1.2;
                    ctx.beginPath();
                    ctx.moveTo(p.x, p.y);
                    ctx.lineTo(p.x - p.len*0.12, p.y + p.len);
                    ctx.stroke();
                    p.y += p.speed; p.x -= p.speed*0.1;
                    if (p.y > H) { p.y = -p.len; p.x = Math.random()*W; }

                } else if (p.type === 'snow') {
                    ctx.fillStyle = `rgba(255,255,255,${p.op})`;
                    ctx.beginPath();
                    ctx.arc(p.x, p.y, p.r, 0, Math.PI*2);
                    ctx.fill();
                    p.y += p.speed; p.x += p.drift;
                    if (p.y > H) { p.y = -p.r; p.x = Math.random()*W; }

                } else if (p.type === 'leaf') {
                    ctx.save();
                    ctx.translate(p.x, p.y);
                    ctx.rotate(p.rot * Math.PI/180);
                    ctx.font = `${p.sz}px serif`;
                    ctx.globalAlpha = 0.85;
                    ctx.fillText(p.emoji, -p.sz*0.5, p.sz*0.5);
                    ctx.restore();
                    p.x += p.drift; p.y += p.speed; p.rot += p.rotSpd;
                    if (p.x > W+30 || p.y > H+30) { p.x = -30; p.y = Math.random()*H*0.6; }
                }
            }
            pw._wxAnimId = pw.requestAnimationFrame(draw);
        }
        draw();
    }
})();
</script>"""
    components.html(_wx_init + _wx_anim, height=0)
