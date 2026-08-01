"""
BIST Sinyal Tarayıcı - Streamlit App
======================================
Rule-based technical analysis signal generator for Borsa Istanbul stocks.

IMPORTANT: This tool does NOT place trades. It only generates buy/sell/hold
signals for you to review and execute manually with your own broker.
This is not investment advice.

Data source: Yahoo Finance (yfinance), which carries BIST tickers with a
".IS" suffix (e.g. THYAO.IS). Data may be delayed and occasionally has
gaps -- always cross-check with your broker's live feed before trading.
"""

import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots

from bist_tickers import BIST_TICKERS, BIST_INDEX_TICKER
from strategy import generate_signals, backtest

st.set_page_config(page_title="BIST Sinyal Tarayıcı", layout="wide", page_icon="📈")

SIGNAL_COLORS = {
    "GÜÇLÜ AL": "#0d7d3f",
    "AL": "#5cb85c",
    "BEKLE": "#9e9e9e",
    "SAT": "#e08a8a",
    "GÜÇLÜ SAT": "#c0392b",
}


# --------------------------------------------------------------------------
# Data fetching
# --------------------------------------------------------------------------
@st.cache_data(ttl=60 * 15, show_spinner=False)
def fetch_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    tk = yf.Ticker(ticker)
    df = tk.history(period=period, interval="1d", auto_adjust=True)
    if df.empty:
        return df
    df.index = df.index.tz_localize(None)
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna()


def fmt_pct(x: float) -> str:
    return f"{x:+.2f}%"


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
st.sidebar.title("📈 BIST Sinyal Tarayıcı")
st.sidebar.caption("Kural tabanlı teknik analiz sinyal aracı")

mode = st.sidebar.radio("Mod", ["Tekil Hisse Analizi", "Toplu Tarama (Watchlist)"])

period = st.sidebar.selectbox(
    "Geçmiş veri aralığı", ["6mo", "1y", "2y", "5y"], index=1,
    help="Göstergelerin (SMA200 gibi) sağlıklı hesaplanması için en az 1 yıl önerilir."
)

st.sidebar.markdown("---")
st.sidebar.subheader("Sinyal Eşikleri")
buy_th = st.sidebar.slider("AL eşiği (skor)", 5, 60, 15, step=5)
sell_th = st.sidebar.slider("SAT eşiği (skor)", -60, -5, -15, step=5)

st.sidebar.markdown("---")
st.sidebar.warning(
    "⚠️ Bu araç yatırım tavsiyesi değildir. Sinyaller geçmiş fiyat/hacim "
    "verisine dayalı kurallardan üretilir, gelecekteki performansı garanti "
    "etmez. Tüm alım/satım kararları ve emirleri kullanıcı tarafından "
    "manuel olarak verilmelidir."
)

# --------------------------------------------------------------------------
# Single stock mode
# --------------------------------------------------------------------------
if mode == "Tekil Hisse Analizi":
    col1, col2 = st.columns([3, 1])
    with col1:
        ticker_names = {f"{v} ({k})": k for k, v in BIST_TICKERS.items()}
        choice = st.selectbox("Hisse seçin", list(ticker_names.keys()))
        ticker = ticker_names[choice]
    with col2:
        custom = st.text_input("veya ticker girin (örn. XXXXX.IS)", "")
        if custom.strip():
            ticker = custom.strip().upper()
            if not ticker.endswith(".IS"):
                ticker += ".IS"

    st.title(f"{ticker}")

    with st.spinner(f"{ticker} için veri indiriliyor..."):
        raw = fetch_history(ticker, period)

    if raw.empty or len(raw) < 60:
        st.error(
            "Veri alınamadı veya yetersiz. Ticker sembolünü kontrol edin "
            "(BIST hisseleri için '.IS' son eki gereklidir, örn. THYAO.IS)."
        )
        st.stop()

    sig_df = generate_signals(raw)
    latest = sig_df.iloc[-1]

    # --- Signal summary card ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Son Kapanış", f"{latest['Close']:.2f} ₺")
    c2.metric("Skor", f"{latest['SCORE']:+d} / 100")
    c3.metric("RSI(14)", f"{latest['RSI14']:.1f}")
    sig_color = SIGNAL_COLORS.get(latest["SIGNAL"], "#333")
    c4.markdown(
        f"<div style='padding:10px;border-radius:8px;background:{sig_color};"
        f"color:white;text-align:center;font-weight:700;font-size:1.1rem;'>"
        f"{latest['SIGNAL']}</div>",
        unsafe_allow_html=True,
    )

    st.markdown("**Sinyal Gerekçeleri:**")
    if latest["REASONS"]:
        for r in latest["REASONS"]:
            st.markdown(f"- {r}")
    else:
        st.markdown("- Belirgin bir sinyal bileşeni tetiklenmedi (nötr bölge)")

    st.caption(
        f"Son güncelleme (veri): {sig_df.index[-1].strftime('%Y-%m-%d')} — "
        "Yahoo Finance verisi gecikmeli olabilir, emir vermeden önce "
        "aracı kurum ekranınızdan teyit edin."
    )

    # --- Chart ---
    st.subheader("Fiyat Grafiği ve Göstergeler")
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True, row_heights=[0.55, 0.2, 0.25],
        vertical_spacing=0.03,
        subplot_titles=("Fiyat + SMA + Bollinger", "RSI(14)", "MACD"),
    )

    fig.add_trace(go.Candlestick(
        x=sig_df.index, open=sig_df["Open"], high=sig_df["High"],
        low=sig_df["Low"], close=sig_df["Close"], name="Fiyat",
        increasing_line_color="#0d7d3f", decreasing_line_color="#c0392b",
    ), row=1, col=1)
    for col, name, dash in [("SMA20", "SMA20", "dot"), ("SMA50", "SMA50", "dash"), ("SMA200", "SMA200", "solid")]:
        fig.add_trace(go.Scatter(x=sig_df.index, y=sig_df[col], name=name,
                                  line=dict(width=1, dash=dash)), row=1, col=1)
    fig.add_trace(go.Scatter(x=sig_df.index, y=sig_df["BB_UPPER"], name="BB Üst",
                              line=dict(width=1, color="rgba(150,150,150,0.5)")), row=1, col=1)
    fig.add_trace(go.Scatter(x=sig_df.index, y=sig_df["BB_LOWER"], name="BB Alt",
                              line=dict(width=1, color="rgba(150,150,150,0.5)"),
                              fill="tonexty", fillcolor="rgba(150,150,150,0.08)"), row=1, col=1)

    fig.add_trace(go.Scatter(x=sig_df.index, y=sig_df["RSI14"], name="RSI14",
                              line=dict(color="#7b5ea7")), row=2, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="#c0392b", row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="#0d7d3f", row=2, col=1)

    fig.add_trace(go.Scatter(x=sig_df.index, y=sig_df["MACD"], name="MACD",
                              line=dict(color="#2980b9")), row=3, col=1)
    fig.add_trace(go.Scatter(x=sig_df.index, y=sig_df["MACD_SIGNAL"], name="Sinyal",
                              line=dict(color="#e67e22")), row=3, col=1)
    fig.add_trace(go.Bar(x=sig_df.index, y=sig_df["MACD_HIST"], name="Histogram",
                          marker_color="rgba(100,100,100,0.4)"), row=3, col=1)

    fig.update_layout(height=800, xaxis_rangeslider_visible=False,
                       legend=dict(orientation="h", y=1.05), margin=dict(t=40))
    st.plotly_chart(fig, use_container_width=True)

    # --- Backtest ---
    st.subheader("Basit Geriye Dönük Test (Backtest)")
    st.caption(
        "Komisyon ve kayma (slippage) hesaba katılmamıştır; gerçek sonuçlar "
        "burada gösterilenden daha düşük olacaktır. Sadece stratejinin "
        "geçmişte nasıl davrandığını görmek içindir, gelecek performansı "
        "garanti etmez."
    )
    bt_df, trades, stats = backtest(sig_df, buy_threshold=buy_th, sell_threshold=sell_th)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Strateji Getirisi", fmt_pct(stats["total_return_pct"]))
    m2.metric("Al-Tut Getirisi", fmt_pct(stats["buy_hold_return_pct"]))
    m3.metric("İşlem Sayısı", stats["num_trades"])
    m4.metric("Kazanma Oranı", f"{stats['win_rate_pct']:.1f}%")
    m5.metric("Maks. Düşüş", fmt_pct(stats["max_drawdown_pct"]))

    eq_fig = go.Figure()
    eq_fig.add_trace(go.Scatter(x=bt_df.index, y=bt_df["EQUITY"], name="Strateji"))
    eq_fig.add_trace(go.Scatter(x=bt_df.index, y=bt_df["BUY_HOLD_EQUITY"], name="Al-Tut",
                                 line=dict(dash="dot")))
    eq_fig.update_layout(height=350, margin=dict(t=20), legend=dict(orientation="h", y=1.1))
    st.plotly_chart(eq_fig, use_container_width=True)

    if trades:
        with st.expander(f"İşlem geçmişi ({len(trades)} işlem)"):
            trades_df = pd.DataFrame(trades)
            trades_df["entry_date"] = pd.to_datetime(trades_df["entry_date"]).dt.strftime("%Y-%m-%d")
            trades_df["exit_date"] = pd.to_datetime(trades_df["exit_date"]).dt.strftime("%Y-%m-%d")
            st.dataframe(trades_df, use_container_width=True)

# --------------------------------------------------------------------------
# Scan mode
# --------------------------------------------------------------------------
else:
    st.title("📋 Toplu Tarama — Watchlist")
    st.caption(
        "Seçili hisse listesi güncel sinyallere göre taranır ve skora göre "
        "sıralanır. Kısa vadeli günlük işlem fikirleri için başlangıç "
        "noktasıdır, tek başına karar kaynağı olarak kullanılmamalıdır."
    )

    default_selection = list(BIST_TICKERS.keys())[:20]
    selected = st.multiselect(
        "Taranacak hisseler",
        options=list(BIST_TICKERS.keys()),
        default=default_selection,
        format_func=lambda t: f"{BIST_TICKERS.get(t, t)} ({t})",
    )

    run = st.button("🔍 Taramayı Başlat", type="primary")

    if run:
        if not selected:
            st.warning("Lütfen en az bir hisse seçin.")
            st.stop()

        results = []
        progress = st.progress(0.0, text="Taranıyor...")
        for i, tk in enumerate(selected):
            try:
                raw = fetch_history(tk, period)
                if raw.empty or len(raw) < 60:
                    continue
                sig_df = generate_signals(raw)
                latest = sig_df.iloc[-1]
                results.append({
                    "Hisse": tk,
                    "Şirket": BIST_TICKERS.get(tk, ""),
                    "Kapanış": round(float(latest["Close"]), 2),
                    "Skor": int(latest["SCORE"]),
                    "Sinyal": latest["SIGNAL"],
                    "RSI14": round(float(latest["RSI14"]), 1),
                    "1G Değişim %": round(
                        float((latest["Close"] / sig_df["Close"].iloc[-2] - 1) * 100), 2
                    ) if len(sig_df) > 1 else None,
                    "Gerekçeler": " | ".join(latest["REASONS"]) if latest["REASONS"] else "-",
                })
            except Exception as e:
                st.caption(f"⚠️ {tk} atlandı: {e}")
            progress.progress((i + 1) / len(selected), text=f"Taranıyor... {tk}")
        progress.empty()

        if not results:
            st.error("Hiçbir hisse için veri alınamadı.")
            st.stop()

        res_df = pd.DataFrame(results).sort_values("Skor", ascending=False).reset_index(drop=True)

        st.subheader("🟢 En Güçlü AL Sinyalleri")
        st.dataframe(
            res_df[res_df["Skor"] >= buy_th].drop(columns=["Gerekçeler"]),
            use_container_width=True, hide_index=True,
        )

        st.subheader("🔴 En Güçlü SAT Sinyalleri")
        st.dataframe(
            res_df[res_df["Skor"] <= sell_th].sort_values("Skor").drop(columns=["Gerekçeler"]),
            use_container_width=True, hide_index=True,
        )

        st.subheader("📊 Tüm Sonuçlar")
        st.dataframe(res_df, use_container_width=True, hide_index=True)

        st.caption(
            f"Tarama zamanı: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')} — "
            "Fiyatlar Yahoo Finance kaynağından günlük kapanış verisidir, "
            "gecikmeli olabilir."
        )

st.markdown("---")
st.caption(
    "BIST Sinyal Tarayıcı — eğitim ve analiz amaçlı bir araçtır, yatırım "
    "danışmanlığı hizmeti değildir. Yatırım kararlarınızdan önce lisanslı "
    "bir yatırım danışmanına başvurun."
)
