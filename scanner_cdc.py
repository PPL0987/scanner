"""
JTS MACD + CDC Scanner v11.0 (CDC Color Edition)
- สแกน SET+MAI ~300 ตัว
- บันทึก OHLC + EMA12/26 + MACD + CDC Color
- CDC Color = Candlestick Color ตามหลักการลุงโฉลก
"""

import yfinance as yf
import requests
import json
from datetime import datetime, timezone, timedelta

WEBHOOK_URL  = "https://n8n.jupetor-cmms.com/webhook/tradingview-jts"
TIMEFRAME    = "1mo"
PERIOD       = "10y"
CHART_MONTHS = 60
THAI_TZ      = timezone(timedelta(hours=7))

SET100 = [
    "PTT.BK","PTTEP.BK","PTTGC.BK","TOP.BK","IRPC.BK","BCP.BK",
    "GULF.BK","GPSC.BK","EGCO.BK","RATCH.BK","BGRIM.BK","BANPU.BK",
    "SCB.BK","KBANK.BK","BBL.BK","KTB.BK","BAY.BK","TTB.BK",
    "TISCO.BK","KKP.BK","TCAP.BK",
    "CPALL.BK","CRC.BK","BJC.BK","HMPRO.BK","COM7.BK","MAKRO.BK",
    "CPF.BK","TU.BK","BTG.BK","GFPT.BK","OSP.BK","CBG.BK",
    "ICHI.BK","OISHI.BK","SAPPE.BK","MALEE.BK","TKN.BK","NRF.BK",
    "LH.BK","AP.BK","QH.BK","SIRI.BK","ORI.BK","SPALI.BK",
    "PSH.BK","SC.BK","NOBLE.BK",
    "BH.BK","BCH.BK","CHG.BK","NTV.BK","BDMS.BK","PR9.BK","RAM.BK",
    "ADVANC.BK","TRUE.BK","JAS.BK","THCOM.BK","DIF.BK","JASIF.BK",
    "AOT.BK","MINT.BK","ERW.BK","CENTEL.BK","AWC.BK","MAJOR.BK",
    "SCC.BK","SCCC.BK","TBSP.BK","TPIPL.BK","IVL.BK","STA.BK",
    "DELTA.BK","KCE.BK","HANA.BK","SVI.BK","BE8.BK","MFEC.BK",
    "SAWAD.BK","MTC.BK","TIDLOR.BK","AEONTS.BK","KTC.BK","TQM.BK",
    "JMART.BK","JMT.BK","SINGER.BK",
    "WHA.BK","AMATA.BK","ROJNA.BK","BEM.BK","BTS.BK","CPN.BK",
    "GLOBAL.BK","RS.BK","VGI.BK","BEAUTY.BK","TNP.BK","NCH.BK",
    "PYLON.BK","ITD.BK","CK.BK","STEC.BK",
]

MAI = [
    "SYNEX.BK","SVOA.BK","SIS.BK","INET.BK","FORTH.BK","AIT.BK",
    "EKH.BK","LPH.BK","VIBHA.BK","WPH.BK","PRINC.BK",
    "SABUY.BK","GEL.BK","CFRESH.BK","ASIAN.BK","MILL.BK",
    "RICHY.BK","MC.BK","MONO.BK","MASTER.BK","CITY.BK",
    "BCPG.BK","SUPER.BK","TPCH.BK","SPCG.BK","ACE.BK","GUNKUL.BK",
    "MEGA.BK","OCC.BK","PAP.BK","PDI.BK",
    "SAT.BK","STANLY.BK","SMIT.BK","TCC.BK","TEAMG.BK",
    "GMM.BK","GRAMMY.BK","JKN.BK","JSP.BK",
    "MBKET.BK","MBK.BK","MSC.BK","NUSA.BK",
    "PLANB.BK","PTG.BK","RCL.BK","RPCX.BK",
    "SAMART.BK","SAUCE.BK","SCN.BK","SEAFCO.BK",
    "SKR.BK","SLP.BK","SMART.BK","SNP.BK",
    "SOHO.BK","SPA.BK","SPRC.BK","SQ.BK",
    "SSP.BK","STAR.BK","SUN.BK","SUSCO.BK",
]

STOCKS = list(dict.fromkeys(SET100 + MAI))

def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calc_macd(close):
    ema12 = ema(close, 12)
    ema26 = ema(close, 26)
    macd  = ema12 - ema26
    sig   = ema(macd, 9)
    hist  = macd - sig
    return macd, sig, hist

def get_cdc_color(ema12_val, ema26_val, open_val, close_val):
    """
    CDC Color Logic - ตามหลักการลุงโฉลก
    🟢 GREEN   = EMA12 > EMA26 AND Close > Open (Strong Bullish)
    🔴 RED     = EMA12 < EMA26 AND Close < Open (Strong Bearish)
    🟡 YELLOW  = EMA12 > EMA26 BUT Close < Open (Bearish candle)
    🟠 ORANGE  = EMA12 < EMA26 BUT Close > Open (Bullish candle)
    """
    is_bullish_ema = ema12_val > ema26_val
    is_bullish_candle = close_val > open_val
    
    if is_bullish_ema and is_bullish_candle:
        return "GREEN"
    elif not is_bullish_ema and not is_bullish_candle:
        return "RED"
    elif is_bullish_ema and not is_bullish_candle:
        return "YELLOW"
    else:
        return "ORANGE"

def scan(df):
    close = df["Close"].squeeze()
    open_p = df["Open"].squeeze()
    if len(close) < 30:
        return None, None, None, {}

    macd_line, sig_line, hist = calc_macd(close)
    position = "NONE"; last_date = None; new_signal = None
    signal_points = []
    bars = len(close)

    for i in range(2, bars):
        m  = macd_line.iloc[i]; s  = sig_line.iloc[i]
        h  = hist.iloc[i];      h1 = hist.iloc[i-1]; h2 = hist.iloc[i-2]
        pm = macd_line.iloc[i-1]; ps = sig_line.iloc[i-1]

        zone_bear     = m < 0 and s < 0
        zone_bull     = m > 0 and s > 0
        cross_up      = pm <= ps and m > s
        cross_down    = pm >= ps and m < s
        pink_to_green = (h1 < 0 and h1 > h2) and (h > 0 and h > h1)
        light_to_red  = (h1 > 0 and h1 < h2) and (h < 0 and h < h1)

        if zone_bear and cross_up and pink_to_green:
            position = "BUY"; last_date = df.index[i]
            signal_points.append({
                "date":  df.index[i].strftime("%Y-%m"),
                "type":  "BUY",
                "price": round(float(df["Close"].iloc[i].item()), 2)
            })
            if i == bars - 1: new_signal = "BUY"

        elif zone_bull and cross_down and light_to_red:
            position = "SELL"; last_date = df.index[i]
            signal_points.append({
                "date":  df.index[i].strftime("%Y-%m"),
                "type":  "SELL",
                "price": round(float(df["Close"].iloc[i].item()), 2)
            })
            if i == bars - 1: new_signal = "SELL"

    # เก็บ 60 เดือนล่าสุด + CDC Color
    df_chart = df.tail(CHART_MONTHS)
    close_c  = df_chart["Close"].squeeze()
    open_c   = df_chart["Open"].squeeze()
    high_c   = df_chart["High"].squeeze()
    low_c    = df_chart["Low"].squeeze()
    ml, sl, hl = calc_macd(close_c)
    e12 = ema(close_c, 12)
    e26 = ema(close_c, 26)

    # คำนวณ CDC Color สำหรับแต่ละแท่งเทียน
    cdc_colors = []
    for j in range(len(df_chart)):
        color = get_cdc_color(
            float(e12.iloc[j]),
            float(e26.iloc[j]),
            float(open_c.iloc[j]),
            float(close_c.iloc[j])
        )
        cdc_colors.append(color)

    chart = {
        "dates":   [d.strftime("%Y-%m") for d in df_chart.index],
        "open":    [round(float(v), 2) for v in open_c],
        "high":    [round(float(v), 2) for v in high_c],
        "low":     [round(float(v), 2) for v in low_c],
        "close":   [round(float(v), 2) for v in close_c],
        "ema12":   [round(float(v), 2) for v in e12],
        "ema26":   [round(float(v), 2) for v in e26],
        "macd":    [round(float(v), 4) for v in ml],
        "signal":  [round(float(v), 4) for v in sl],
        "hist":    [round(float(v), 4) for v in hl],
        "cdc_color": cdc_colors,  # ✅ สีแท่งเทียน CDC
        "signals": [s for s in signal_points if s["date"] >= df_chart.index[0].strftime("%Y-%m")]
    }

    return position, last_date, new_signal, chart

def send_line(symbol, signal, price, last_date):
    name     = symbol.replace(".BK", "")
    emoji    = "⚠️" if signal == "BUY" else "🔴"
    label    = "Ready to Buy" if signal == "BUY" else "Ready to Sell"
    now_thai = datetime.now(THAI_TZ).strftime('%d/%m/%Y %H:%M')
    payload  = {
        "symbol": name, "signal": signal, "price": round(price, 2),
        "message": (
            f"{emoji} {label} — {name}\n"
            f"ราคา: {round(price, 2)} บาท\n"
            f"Timeframe: Monthly\n"
            f"สัญญาณ: {last_date.strftime('%m/%Y') if last_date else '-'}\n"
            f"เวลา: {now_thai}"
        ),
        "time": datetime.now(THAI_TZ).strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        r = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        print(f"    → LINE: {r.status_code}")
    except Exception as e:
        print(f"    → LINE error: {e}")

def save_json(results):
    data = {
        "updated": datetime.now(THAI_TZ).strftime('%d/%m/%Y %H:%M'),
        "stocks":  results
    }
    with open("scanner-data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n  → บันทึก scanner-data.json ({len(results)} ตัว)")

def main():
    now_thai = datetime.now(THAI_TZ).strftime('%d/%m/%Y %H:%M:%S')
    print(f"\n{'='*60}")
    print(f"  JTS MACD + CDC Scanner v11.0 — Monthly ({len(STOCKS)} หุ้น)")
    print(f"  CDC Color Edition (ลุงโฉลก)")
    print(f"  {now_thai}")
    print(f"{'='*60}\n")

    results = []

    for i, symbol in enumerate(STOCKS, 1):
        print(f"[{i:3d}/{len(STOCKS)}] {symbol:<15}", end=" ")
        try:
            df = yf.download(symbol, period=PERIOD, interval=TIMEFRAME,
                             progress=False, auto_adjust=True)
            if df.empty or len(df) < 30:
                print("⚠️  ข้อมูลน้อย"); continue

            position, last_date, new_signal, chart = scan(df)
            price    = float(df["Close"].iloc[-1].item())
            icon     = "🟢" if position == "BUY" else "🔴" if position == "SELL" else "⬜"
            date_str = last_date.strftime("%m/%Y") if last_date else "-"
            new      = " ← ใหม่!" if new_signal else ""

            print(f"{icon} {str(position):<5} (ล่าสุด: {date_str}){new}")

            results.append({
                "symbol":   symbol.replace(".BK", ""),
                "position": position,
                "date":     date_str,
                "price":    round(price, 2),
                "new":      bool(new_signal),
                "chart":    chart
            })

            if position in ("BUY", "SELL"):
                send_line(symbol, position, price, last_date)

        except Exception as e:
            print(f"❌ {e}")

    save_json(results)

    buy_list  = [r for r in results if r["position"] == "BUY"]
    sell_list = [r for r in results if r["position"] == "SELL"]
    new_list  = [r for r in results if r["new"]]

    print(f"\n{'='*60}")
    print(f"  สรุป: BUY {len(buy_list)} | SELL {len(sell_list)} | ใหม่ {len(new_list)}")
    print(f"  CDC Color: 🟢 GREEN | 🔴 RED | 🟡 YELLOW | 🟠 ORANGE")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
