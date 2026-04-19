#!/usr/bin/env python3
"""
Now TV Sports EPG - 自动抓取 + Telegram 5分钟提醒
================================================
依赖：pip install requests beautifulsoup4

用法：
  1. pip install requests beautifulsoup4
  2. 填写 BOT_TOKEN 和 CHAT_ID
  3. python nowtv_reminder_auto.py

每 3 分钟自动抓取 nowplayer.now.com 节目表，
命中"开播前 5 分钟"窗口时推送 Telegram 提醒。
"""

import time
import json
import re
import requests
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# ── 配置区（只需改这里）────────────────────────────────────────────────────
BOT_TOKEN      = "YOUR_BOT_TOKEN"   # 从 @BotFather 获取
CHAT_ID        = "YOUR_CHAT_ID"     # 你的 Telegram chat_id（数字字符串）
REMIND_MINUTES = 5                  # 提前几分钟提醒
FETCH_INTERVAL = 180                # 抓取间隔（秒），推荐 180 = 3 分钟
HKT            = timezone(timedelta(hours=8))

# 要监控的频道（Now TV 体育频道 ID）
CHANNEL_IDS = ["611", "621", "622", "623", "630", "631", "635", "680"]

# 关键词过滤（留空 = 全部节目都提醒；填关键词只提醒匹配的）
# 示例：KEYWORDS = ["PL Goals", "Century Break", "Badminton", "NBA", "直播"]
KEYWORDS = []
# ───────────────────────────────────────────────────────────────────────────

BASE_URL  = "https://nowplayer.now.com"
HEADERS   = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "zh-HK,zh;q=0.9,en;q=0.8",
    "Referer": BASE_URL,
}

CHANNEL_NAMES = {
    "611": "Now Sports 4K 1",
    "621": "Premier League 1",
    "622": "Premier League 2",
    "623": "Premier League 3",
    "630": "Now Sports Prime",
    "631": "Now Sports Prime 2",
    "635": "Now Sports 5",
    "680": "Now Sports Plus",
}


# ── 抓取节目表 ───────────────────────────────────────────────────────────────

def fetch_channel_programs(channel_id: str) -> list:
    """抓取单个频道的节目（今天 + 明天 + 后天）"""
    programs = []
    for day_offset in range(3):
        url = f"{BASE_URL}/tvguide/channeldetail/{channel_id}/{day_offset}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")

            # 方式1：__NEXT_DATA__ JSON
            for script in soup.find_all("script"):
                text = script.string or ""
                if "__NEXT_DATA__" in text:
                    m = re.search(r'__NEXT_DATA__\s*=\s*(\{.*\})', text, re.S)
                    if m:
                        try:
                            data = json.loads(m.group(1))
                            progs = (data.get("props", {})
                                        .get("pageProps", {})
                                        .get("programList", []))
                            for p in progs:
                                programs.append({
                                    "ch":    channel_id,
                                    "title": p.get("programName", "").strip(),
                                    "start": p.get("startTime", ""),
                                    "end":   p.get("endTime", ""),
                                    "live":  bool(p.get("isLive") or p.get("liveTag")),
                                })
                        except Exception:
                            pass

            # 方式2：inline JSON arrays with startTime
            if not programs:
                for script in soup.find_all("script"):
                    text = script.string or ""
                    matches = re.findall(
                        r'\{"programName"\s*:\s*"([^"]+)"[^}]*"startTime"\s*:\s*"([^"]+)"[^}]*\}',
                        text
                    )
                    for title, start in matches:
                        programs.append({
                            "ch": channel_id, "title": title.strip(),
                            "start": start, "end": "", "live": False,
                        })

            # 方式3：HTML 节点解析
            if not programs:
                for item in soup.select("[data-start], [data-time]"):
                    title = item.get_text(strip=True)
                    start = item.get("data-start") or item.get("data-time", "")
                    if title and start:
                        programs.append({
                            "ch": channel_id, "title": title,
                            "start": start, "end": "", "live": False,
                        })

        except requests.RequestException as e:
            print(f"  [警告] CH {channel_id} day={day_offset}: {e}")
    return programs


def fetch_all_programs() -> list:
    all_progs = []
    for ch_id in CHANNEL_IDS:
        progs = fetch_channel_programs(ch_id)
        # 解析时间
        for p in progs:
            dt = parse_time(p["start"])
            if dt:
                p["dt"] = dt
                all_progs.append(p)
        print(f"  CH {ch_id} → {len(progs)} 个节目")
        time.sleep(1.5)
    all_progs.sort(key=lambda x: x["dt"])
    return all_progs


def parse_time(raw: str):
    if not raw:
        return None
    raw = str(raw).strip()
    for fmt in [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M",
    ]:
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=HKT)
            return dt
        except ValueError:
            pass
    try:
        ts = int(raw)
        if ts > 1e12:
            ts //= 1000
        return datetime.fromtimestamp(ts, tz=HKT)
    except (ValueError, OSError):
        pass
    return None


# ── 内置备用节目表（抓取失败时使用）────────────────────────────────────────

FALLBACK_PROGRAMS = [
    {"ch":"621","title":"Premier League 25/26 - Everton vs Liverpool",           "start":"2026-04-19 20:30","live":True},
    {"ch":"621","title":"Premier League 25/26 - Man City vs Arsenal",             "start":"2026-04-19 23:00","live":True},
    {"ch":"611","title":"[4K] Premier League 25/26 - Man City vs Arsenal",        "start":"2026-04-19 23:00","live":True},
    {"ch":"630","title":"Century Break 2026 E32",                                 "start":"2026-04-20 04:00","live":False},
    {"ch":"630","title":"PL Goals 25/26 - Week 25",                               "start":"2026-04-20 05:15","live":False},
    {"ch":"630","title":"Badminton Unlimited 2026 E37",                           "start":"2026-04-21 07:00","live":False},
    {"ch":"635","title":"Barclays WSL 25/26 - Arsenal v Man City",                "start":"2026-04-20 07:55","live":True},
    {"ch":"630","title":"ATP 26 Delray Beach Open QF - C.Wong vs F.Cobolli",      "start":"2026-04-20 02:00","live":True},
    {"ch":"630","title":"PGA TOUR Highlights 2026 E4",                            "start":"2026-04-20 05:30","live":False},
    {"ch":"630","title":"Premier League Highlights 25/26 - Week 25",              "start":"2026-04-20 12:00","live":False},
]

def load_fallback() -> list:
    progs = []
    for p in FALLBACK_PROGRAMS:
        dt = parse_time(p["start"])
        if dt:
            p2 = dict(p)
            p2["dt"] = dt
            progs.append(p2)
    return progs


# ── Telegram 发送 ────────────────────────────────────────────────────────────

def send_telegram(text: str) -> bool:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(
            url,
            data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        if r.ok:
            return True
        print(f"  [TG 失败] {r.status_code}: {r.text[:200]}")
    except requests.RequestException as e:
        print(f"  [TG 网络错误] {e}")
    return False


def build_message(p: dict) -> str:
    icon = "🔴" if p.get("live") else "📺"
    kind = "直播即将开始 🔥" if p.get("live") else "即将播出"
    t_str = p["dt"].strftime("%m/%d（%a）%H:%M HKT")
    ch_label = CHANNEL_NAMES.get(p["ch"], f"CH {p['ch']}")
    return (
        f"{icon} <b>Now TV Sports · 开播前 {REMIND_MINUTES} 分钟提醒</b>\n\n"
        f"🎯 <b>{p['title']}</b>\n"
        f"📡 频道：CH {p['ch']} {ch_label}\n"
        f"🕐 时间：{t_str}\n"
        f"⚡ 状态：{kind}\n\n"
        f'🔗 <a href="https://nowplayer.now.com/sports/schedule">打开节目表</a>'
    )


def match_keywords(title: str) -> bool:
    if not KEYWORDS:
        return True
    tl = title.lower()
    return any(kw.lower() in tl for kw in KEYWORDS)


def now_hkt_str() -> str:
    return datetime.now(tz=HKT).strftime("%H:%M:%S HKT")


# ── 主循环 ────────────────────────────────────────────────────────────────────

def main():
    sent: set = set()
    programs: list = []
    last_fetch: float = 0.0

    print("=" * 55)
    print(" Now TV Sports EPG 自动抓取 + Telegram 提醒")
    print(f" 提前 {REMIND_MINUTES} 分钟提醒 | 每 {FETCH_INTERVAL//60} 分钟抓取")
    print(f" 监控频道：{', '.join('CH '+c for c in CHANNEL_IDS)}")
    print(f" 关键词过滤：{'全部节目' if not KEYWORDS else KEYWORDS}")
    print("=" * 55)

    send_telegram(
        f"✅ <b>Now TV Sports 提醒已启动</b>\n"
        f"提前 {REMIND_MINUTES} 分钟推送 · 每 {FETCH_INTERVAL//60} 分钟抓取节目表\n"
        f'🔗 <a href="https://nowplayer.now.com/sports/schedule">节目表</a>'
    )

    while True:
        now_ts = time.time()

        # ── 3 分钟重新抓取节目表 ──────────────────────────────────────────
        if now_ts - last_fetch >= FETCH_INTERVAL:
            print(f"\n[{now_hkt_str()}] 开始抓取节目表...")
            try:
                fresh = fetch_all_programs()
                if fresh:
                    programs = fresh
                    print(f"[{now_hkt_str()}] 抓取完成，共 {len(programs)} 个节目")
                else:
                    print(f"[{now_hkt_str()}] 抓取结果为空，使用备用节目表")
                    if not programs:
                        programs = load_fallback()
            except Exception as e:
                print(f"[{now_hkt_str()}] 抓取异常：{e}，使用备用节目表")
                if not programs:
                    programs = load_fallback()
            last_fetch = now_ts

        # ── 每 30 秒检查提醒窗口 ──────────────────────────────────────────
        now_dt = datetime.now(tz=HKT)
        hi = REMIND_MINUTES * 60          # 300 秒
        lo = (REMIND_MINUTES - 1) * 60   # 240 秒（容差 1 分钟）

        for p in programs:
            key = f"{p['ch']}|{p['start']}|{p['title']}"
            if key in sent:
                continue
            if not match_keywords(p["title"]):
                continue
            diff = (p["dt"] - now_dt).total_seconds()
            if lo < diff <= hi:
                if send_telegram(build_message(p)):
                    sent.add(key)
                    print(f"[{now_hkt_str()}] ✅ 已提醒：{p['title']} (CH {p['ch']})")

        time.sleep(30)


if __name__ == "__main__":
    main()
