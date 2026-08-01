"""
Rule-based, fully transparent signal engine.
No black box: every point added/subtracted from the score has a stated reason.

Score range: -100 (strong sell) .. +100 (strong buy)
"""
import numpy as np
import pandas as pd

from indicators import sma, rsi, macd, bollinger_bands, atr, volume_ratio


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["SMA20"] = sma(df["Close"], 20)
    df["SMA50"] = sma(df["Close"], 50)
    df["SMA200"] = sma(df["Close"], 200)
    df["RSI14"] = rsi(df["Close"], 14)
    macd_line, signal_line, hist = macd(df["Close"])
    df["MACD"] = macd_line
    df["MACD_SIGNAL"] = signal_line
    df["MACD_HIST"] = hist
    upper, mid, lower = bollinger_bands(df["Close"])
    df["BB_UPPER"] = upper
    df["BB_MID"] = mid
    df["BB_LOWER"] = lower
    df["ATR14"] = atr(df)
    df["VOL_RATIO"] = volume_ratio(df["Volume"])
    return df


def score_row(row) -> tuple[int, list[str]]:
    score = 0
    reasons = []

    # --- Trend (SMA stack) ---
    if pd.notna(row["SMA50"]) and pd.notna(row["SMA200"]):
        if row["Close"] > row["SMA50"] > row["SMA200"]:
            score += 25
            reasons.append("Fiyat SMA50 ve SMA200 üzerinde (güçlü yükseliş trendi)")
        elif row["Close"] < row["SMA50"] < row["SMA200"]:
            score -= 25
            reasons.append("Fiyat SMA50 ve SMA200 altında (güçlü düşüş trendi)")
        elif row["Close"] > row["SMA50"]:
            score += 10
            reasons.append("Fiyat SMA50 üzerinde")
        elif row["Close"] < row["SMA50"]:
            score -= 10
            reasons.append("Fiyat SMA50 altında")

    # --- Momentum (RSI) ---
    if pd.notna(row["RSI14"]):
        if row["RSI14"] < 30:
            score += 20
            reasons.append(f"RSI aşırı satım bölgesinde ({row['RSI14']:.1f})")
        elif row["RSI14"] > 70:
            score -= 20
            reasons.append(f"RSI aşırı alım bölgesinde ({row['RSI14']:.1f})")
        elif row["RSI14"] < 45:
            score += 5
        elif row["RSI14"] > 55:
            score -= 5

    # --- MACD ---
    if pd.notna(row["MACD"]) and pd.notna(row["MACD_SIGNAL"]):
        if row["MACD"] > row["MACD_SIGNAL"] and row["MACD_HIST"] > 0:
            score += 20
            reasons.append("MACD sinyal çizgisi üzerinde (pozitif momentum)")
        elif row["MACD"] < row["MACD_SIGNAL"] and row["MACD_HIST"] < 0:
            score -= 20
            reasons.append("MACD sinyal çizgisi altında (negatif momentum)")

    # --- Bollinger Bands (mean reversion) ---
    if pd.notna(row["BB_LOWER"]) and pd.notna(row["BB_UPPER"]):
        if row["Close"] <= row["BB_LOWER"]:
            score += 15
            reasons.append("Fiyat alt Bollinger bandına yakın/altında")
        elif row["Close"] >= row["BB_UPPER"]:
            score -= 15
            reasons.append("Fiyat üst Bollinger bandına yakın/üzerinde")

    # --- Volume confirmation ---
    if pd.notna(row["VOL_RATIO"]):
        if row["VOL_RATIO"] > 1.5 and score > 0:
            score += 10
            reasons.append(f"Hacim ortalamanın {row['VOL_RATIO']:.1f}x üzerinde (teyit)")
        elif row["VOL_RATIO"] > 1.5 and score < 0:
            score -= 10
            reasons.append(f"Hacim ortalamanın {row['VOL_RATIO']:.1f}x üzerinde (teyit)")

    score = int(max(-100, min(100, score)))
    return score, reasons


def classify_signal(score: int) -> str:
    if score >= 40:
        return "GÜÇLÜ AL"
    elif score >= 15:
        return "AL"
    elif score > -15:
        return "BEKLE"
    elif score > -40:
        return "SAT"
    else:
        return "GÜÇLÜ SAT"


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    df = add_indicators(df)
    scores, all_reasons = [], []
    for _, row in df.iterrows():
        s, r = score_row(row)
        scores.append(s)
        all_reasons.append(r)
    df["SCORE"] = scores
    df["SIGNAL"] = df["SCORE"].apply(classify_signal)
    df["REASONS"] = all_reasons
    return df


def backtest(
    df: pd.DataFrame,
    buy_threshold: int = 15,
    sell_threshold: int = -15,
    initial_capital: float = 100_000.0,
):
    """
    Long-only, single-position backtest:
    - Enter when SCORE >= buy_threshold and flat
    - Exit when SCORE <= sell_threshold and holding
    Commission/slippage NOT modelled -> real results will be worse than shown.
    """
    df = df.copy()
    dates = df.index

    position_shares = 0.0
    cash = initial_capital
    entry_price = None
    entry_date = None
    trades = []
    equity_curve = []

    closes = df["Close"].values
    scores = df["SCORE"].values

    for i in range(len(df)):
        price = closes[i]
        score = scores[i]

        if position_shares == 0 and score >= buy_threshold:
            position_shares = cash / price
            entry_price = price
            entry_date = dates[i]
            cash = 0.0
        elif position_shares > 0 and score <= sell_threshold:
            cash = position_shares * price
            trades.append(
                {
                    "entry_date": entry_date,
                    "entry_price": round(float(entry_price), 2),
                    "exit_date": dates[i],
                    "exit_price": round(float(price), 2),
                    "return_pct": round((price / entry_price - 1) * 100, 2),
                }
            )
            position_shares = 0.0

        equity = cash if position_shares == 0 else position_shares * price
        equity_curve.append(equity)

    df["EQUITY"] = equity_curve

    bh_shares = initial_capital / closes[0]
    df["BUY_HOLD_EQUITY"] = bh_shares * closes

    total_return = (df["EQUITY"].iloc[-1] / initial_capital - 1) * 100
    bh_return = (df["BUY_HOLD_EQUITY"].iloc[-1] / initial_capital - 1) * 100
    win_trades = [t for t in trades if t["return_pct"] > 0]
    win_rate = (len(win_trades) / len(trades) * 100) if trades else 0.0

    running_max = df["EQUITY"].cummax()
    drawdown = (df["EQUITY"] - running_max) / running_max * 100
    max_dd = drawdown.min() if len(drawdown) else 0.0

    stats = {
        "total_return_pct": round(float(total_return), 2),
        "buy_hold_return_pct": round(float(bh_return), 2),
        "num_trades": len(trades),
        "win_rate_pct": round(float(win_rate), 2),
        "max_drawdown_pct": round(float(max_dd), 2),
    }
    return df, trades, stats
