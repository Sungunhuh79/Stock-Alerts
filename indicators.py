import numpy as np
import yfinance as yf

RSI_OVERSOLD   = 30
RSI_OVERBOUGHT = 70
BB_PERIOD      = 20
BB_STD         = 2.0
SMA200_PERIOD  = 200
SMA_PROX_PCT   = 3.0
SMA_CONFIRM    = 2

def get_price_data(ticker, days=250):
    data = yf.download(ticker, period=f"{days}d", interval="1d", progress=False)
    return data["Close"].values.flatten()

def calculate_rsi(prices, period=14):
    deltas = np.diff(prices)
    gains  = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_g  = np.mean(gains[:period])
    avg_l  = np.mean(losses[:period])
    for i in range(period, len(gains)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
    rs = avg_g / avg_l if avg_l != 0 else 100
    return round(100 - (100 / (1 + rs)), 2)

def calculate_bollinger(prices, period=BB_PERIOD, std_mult=BB_STD):
    window = prices[-period:]
    sma    = np.mean(window)
    std    = np.std(window)
    return round(sma + std_mult*std, 2), round(sma, 2), round(sma - std_mult*std, 2)

def calculate_sma200(prices):
    if len(prices) < SMA200_PERIOD:
        return round(float(np.mean(prices)), 2)
    return round(float(np.mean(prices[-SMA200_PERIOD:])), 2)

def check_sma200_cross(prices, confirm_days=SMA_CONFIRM):
    if len(prices) < SMA200_PERIOD + confirm_days:
        return "NONE", 0.0
    sma_now  = np.mean(prices[-SMA200_PERIOD:])
    sma_prev = np.mean(prices[-(SMA200_PERIOD + confirm_days):-confirm_days])
    recent   = prices[-confirm_days:]
    old_ref  = prices[-(confirm_days * 2):-confirm_days]
    if all(p > sma_now for p in recent) and all(p < sma_prev for p in old_ref):
        return "CROSSED_ABOVE", round(float(sma_now), 2)
    if all(p < sma_now for p in recent) and all(p > sma_prev for p in old_ref):
        return "CROSSED_BELOW", round(float(sma_now), 2)
    return "NONE", round(float(sma_now), 2)

def check_all(ticker):
    prices  = get_price_data(ticker)
    price   = round(float(prices[-1]), 2)
    rsi     = calculate_rsi(prices)
    bb_up, bb_mid, bb_lo = calculate_bollinger(prices)
    sma200  = calculate_sma200(prices)
    cross, _ = check_sma200_cross(prices)
    pct_from_sma = round((price - sma200) / sma200 * 100, 2)
    near_sma = abs(pct_from_sma) <= SMA_PROX_PCT
    alerts   = []
    priority = "NORMAL"
    if rsi < RSI_OVERSOLD:
        alerts.append(f"RSI OVERSOLD: {rsi} (below {RSI_OVERSOLD})")
        priority = "HIGH"
    if rsi > RSI_OVERBOUGHT:
        alerts.append(f"RSI OVERBOUGHT: {rsi} (above {RSI_OVERBOUGHT})")
        priority = "HIGH"
    if price < bb_lo:
        alerts.append(f"BELOW LOWER BOLLINGER BAND (price ${price} < ${bb_lo})")
        priority = "HIGH"
    if price > bb_up:
        alerts.append(f"ABOVE UPPER BOLLINGER BAND (price ${price} > ${bb_up})")
    if cross == "CROSSED_BELOW":
        alerts.append(f"CROSSED BELOW 200 SMA — death cross (SMA: ${sma200})")
        priority = "HIGH"
    elif cross == "CROSSED_ABOVE":
        alerts.append(f"RECLAIMED 200 SMA — golden cross (SMA: ${sma200})")
    elif near_sma:
        direction = "above" if price > sma200 else "below"
        alerts.append(f"NEAR 200 SMA: {abs(pct_from_sma):.1f}% {direction} (price ${price}, SMA ${sma200})")
    return {
        "ticker": ticker, "price": price, "rsi": rsi,
        "bb_upper": bb_up, "bb_mid": bb_mid, "bb_lower": bb_lo,
        "sma200": sma200, "pct_from_sma": pct_from_sma,
        "sma_cross": cross, "near_sma": near_sma,
        "alerts": alerts, "priority": priority,
        "triggered": len(alerts) > 0,
    }
