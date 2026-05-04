#!/usr/bin/env python3
"""
Now TV Sports EPG - 自动抓取 + Telegram 5分钟提醒
================================================
依赖：pip install requests

用法：
  1. pip install requests
  2. 填写 BOT_TOKEN 和 CHAT_ID
  3. python nowtv_reminder_auto.py

每 3 分钟抓取一次频道节目时间表，
对即将开播（前 5 分钟）的节目调用详情 API 获取节目名，
再推送 Telegram 提醒。
"""

import re
import time
import requests
from datetime import datetime, timezone, timedelta

# ── 配置区（只需改这里）────────────────────────────────────────────────────────
BOT_TOKEN      = "YOUR_BOT_TOKEN"   # 从 @BotFather 获取
CHAT_ID        = ["YOUR_CHAT_ID"]   # 支持多个，例如 ["123456", "-1009999999"]
REMIND_MINUTES = 5                  # 提前几分钟提醒
WINDOW_MINUTES = 3                  # 提醒窗口宽度（分钟），建议 >= 抓取间隔
FETCH_INTERVAL = 180                # 节目表刷新间隔（秒）

CHANNEL_IDS = [
    "611", "612",
    "621", "622", "623",
    "630", "631", "632", "633", "634", "635", "636", "637", "638", "639",
    "640", "641", "643",
    "647",
    "668",
    "680",
    "683", "684",
]

# 关键词过滤（留空 = 全部节目；填关键词只提醒匹配的）
KEYWORDS = []
# ───────────────────────────────────────────────────────────────────────────────

BASE_URL = "https://nowplayer.now.com"
HKT      = timezone(timedelta(hours=8))

CHANNEL_NAMES = {
    "611": "Now Sports 4K 1",
    "612": "Now Sports 4K 2",
    "621": "Premier League 1",
    "622": "Premier League 2",
    "623": "Premier League 3",
    "630": "Now Sports Prime",
    "631": "Now Sports Prime 2",
    "632": "Now Sports 2",
    "633": "Now Sports 3",
    "634": "Now Sports 4",
    "635": "Now Sports 5",
    "636": "Now Sports 6",
    "637": "Now Sports 7",
    "638": "Now Sports 8",
    "639": "Now Sports 9",
    "640": "MUTV",
    "641": "NBA",
    "643": "Now Sports Racing",
    "647": "Now Sports Moto",
    "668": "Now Sports Horse Racing",
    "680": "Now Sports Plus",
    "683": "Now Golf",
    "684": "Now Golf 2",
}

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-HK,zh;q=0.9,en;q=0.8",
    "Upgrade-Insecure-Requests": "1",
}


# ── Session Cookie ──────────────────────────────────────────────────────────────

def get_session_cookie() -> dict:
    """访问首页获取 session cookie，让服务器认为是真实浏览器。"""
    try:
        resp = requests.get(f"{BASE_URL}/tvguide", headers=BASE_HEADERS, timeout=15)
        return resp.cookies.get_dict()
    except Exception as e:
        print(f"  [警告] 获取 session cookie 失败: {e}")
        return {}


# ── 时间解析 ────────────────────────────────────────────────────────────────────

def parse_12hour(time_str: str, date_str: str):
    """解析 '12:00AM' + '2026-05-03' → datetime（HKT）"""
    m = re.match(r'^(\d{1,2}):(\d{2})(AM|PM)$', time_str, re.I)
    if not m:
        return None
    h, mi, ampm = int(m[1]), int(m[2]), m[3].upper()
    if ampm == "AM" and h == 12:
        h = 0
    if ampm == "PM" and h != 12:
        h += 12
    try:
        return datetime.fromisoformat(f"{date_str}T{h:02d}:{mi:02d}:00+08:00")
    except ValueError:
        return None


# ── 抓取频道节目时间表（只需 ID + 时间，不需要节目名）──────────────────────────

def fetch_schedule_items(channel_id: str, cookies: dict) -> list:
    """
    返回列表：[{"id": "...", "time_str": "12:00AM", "dt": datetime, "date_str": "2026-05-03"}]
    """
    items = []
    now_hkt = datetime.now(tz=HKT)
    cur_year, cur_month, cur_day = now_hkt.year, now_hkt.month - 1, now_hkt.day  # month 0-indexed

    for week in range(2):  # week=0 本周，week=1 下周
        url = f"{BASE_URL}/tvguide/channeldetail/{channel_id}/{week}"
        try:
            resp = requests.get(url, headers=BASE_HEADERS, cookies=cookies, timeout=15)
            if resp.status_code != 200:
                continue
            html = resp.text

            # 提取周标签日期：id="week1" → day number
            week_dates = {}
            for m in re.finditer(r'id="week(\d+)"[\s\S]{1,400}?<br>(\d+)</div>', html):
                week_num = int(m.group(1))
                d = int(m.group(2))
                month = cur_month
                if d < cur_day - 20:
                    month = (cur_month + 1) % 12
                if d > cur_day + 20:
                    month = (cur_month - 1) % 12
                year = cur_year + 1 if (month == 0 and cur_month == 11) else cur_year
                week_dates[week_num] = f"{year}-{month+1:02d}-{d:02d}"

            # 按日期区块分割
            parts = re.split(r'<div\s+id="day(\d+)"\s+class="all-data-day[^"]*"[^>]*>', html)
            i = 1
            while i < len(parts):
                day_num = int(parts[i])
                day_content = parts[i + 1] if i + 1 < len(parts) else ""
                date_str = week_dates.get(day_num)
                if not date_str:
                    i += 2
                    continue

                for li_m in re.finditer(r'<li\s+id="(\d+)"[^>]*>([\s\S]*?)</li>', day_content):
                    li_id = li_m.group(1)
                    li_body = li_m.group(2)
                    time_m = re.search(r'<div[^>]*class="time"[^>]*>(\d{1,2}:\d{2}(?:AM|PM))</div>',
                                       li_body, re.I)
                    if not time_m:
                        continue
                    dt = parse_12hour(time_m.group(1), date_str)
                    if dt:
                        items.append({
                            "id": li_id,
                            "time_str": time_m.group(1),
                            "dt": dt,
                            "date_str": date_str,
                        })
                i += 2

        except Exception as e:
            print(f"  [警告] CH {channel_id} week={week}: {e}")

    return items


# ── 调用详情 API 获取节目名 ──────────────────────────────────────────────────────

def fetch_program_detail(program_id: str, cookies: dict) -> dict | None:
    """调用 /tvguide/epgprogramdetail 获取节目名和直播状态。"""
    url = f"{BASE_URL}/tvguide/epgprogramdetail"
    headers = {**BASE_HEADERS, "X-Requested-With": "XMLHttpRequest",
               "Accept": "application/json, text/javascript, */*"}
    try:
        resp = requests.get(url, params={"programId": program_id},
                            headers=headers, cookies=cookies, timeout=10)
        if not resp.ok:
            return None
        data = resp.json()
        series = (data.get("chiSeriesName") or data.get("engSeriesName") or "").strip()
        prog   = (data.get("chiProgName")   or data.get("engProgName")   or "").strip()
        if not prog:
            title = series
        elif series and not prog.startswith(series):
            title = f"{series} {prog}".strip()
        else:
            title = prog
        if not title or "请留意下播映赛事" in title:
            return None
        is_live = data.get("isLive") in ("Y", True)
        image_url = (
            data.get("chiImageUrl") or data.get("engImageUrl") or
            data.get("programImage") or data.get("imageUrl") or
            data.get("horizontalImageUrl") or data.get("landscapeImageUrl") or
            data.get("image") or data.get("thumbnail") or ""
        ).strip()
        return {"title": title, "live": is_live, "image_url": image_url}
    except Exception as e:
        print(f"  [警告] 详情 API {program_id}: {e}")
        return None


# ── Telegram 发送 ────────────────────────────────────────────────────────────────

def send_telegram(text: str, image_url: str = "") -> bool:
    all_ok = True
    for chat_id in (CHAT_ID if isinstance(CHAT_ID, list) else [CHAT_ID]):
        try:
            ok = False
            if image_url:
                r = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                    json={"chat_id": chat_id, "photo": image_url, "caption": text, "parse_mode": "HTML"},
                    timeout=10,
                )
                ok = r.ok
                if not ok:
                    print(f"  [sendPhoto失败({r.status_code})] 降级文字消息")
            if not ok:
                r = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                    timeout=10,
                )
                if not r.ok:
                    print(f"  [TG 失败] chat={chat_id} {r.status_code}: {r.text[:200]}")
                    all_ok = False
        except Exception as e:
            print(f"  [TG 网络错误] chat={chat_id}: {e}")
            all_ok = False
    return all_ok


SPORT_EMOJI = {
    "611": "⚽", "612": "🏎️",
    "621": "⚽", "622": "⚽", "623": "⚽",
    "630": "🏅", "631": "🏅",
    "632": "⚽", "633": "⚽",
    "634": "🎾", "635": "🏅", "636": "🎾",
    "637": "🎱", "638": "🏅", "639": "🏅",
    "640": "⚽", "641": "🏀", "643": "🏎️",
    "647": "🏍️", "668": "🐴", "680": "🏅",
    "683": "⛳", "684": "⛳",
}


def build_message(ch: str, title: str, is_live: bool, dt: datetime) -> str:
    live_icon = "🔴" if is_live else "📺"
    live_text = "直播即将开始 🔥" if is_live else "即将播出"
    sport_emoji = SPORT_EMOJI.get(ch, "📺")
    t_str = dt.strftime("%m/%d（%a）%H:%M HKT")
    ch_label = CHANNEL_NAMES.get(ch, f"CH {ch}")
    return (
        f"{live_icon} <b>{live_text}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{sport_emoji} <b>{title}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📡 CH {ch} · {ch_label}\n"
        f"🕐 {t_str}\n\n"
        f"<i>Now TV Sports · 开播前 {REMIND_MINUTES} 分钟提醒</i>"
    )


def match_keywords(title: str) -> bool:
    if not KEYWORDS:
        return True
    return any(kw.lower() in title.lower() for kw in KEYWORDS)


def now_hkt_str() -> str:
    return datetime.now(tz=HKT).strftime("%H:%M:%S HKT")


# ── 主循环 ────────────────────────────────────────────────────────────────────────

def main():
    sent: set = set()
    schedule: dict = {}   # {ch_id: [items]}
    last_fetch: float = 0.0
    cookies: dict = {}

    print("=" * 60)
    print(" Now TV Sports EPG 自动抓取 + Telegram 提醒")
    print(f" 提前 {REMIND_MINUTES} 分钟提醒 | 每 {FETCH_INTERVAL // 60} 分钟刷新")
    print(f" 监控频道：{', '.join('CH ' + c for c in CHANNEL_IDS)}")
    print(f" 关键词过滤：{'全部节目' if not KEYWORDS else KEYWORDS}")
    print("=" * 60)

    send_telegram(
        f"✅ <b>Now TV Sports 提醒已启动</b>\n"
        f"提前 {REMIND_MINUTES} 分钟推送 · 每 {FETCH_INTERVAL // 60} 分钟刷新节目表"
    )

    while True:
        now_ts = time.time()

        # ── 定时刷新节目时间表 ────────────────────────────────────────────────
        if now_ts - last_fetch >= FETCH_INTERVAL:
            print(f"\n[{now_hkt_str()}] 刷新节目表...")
            cookies = get_session_cookie()
            for ch_id in CHANNEL_IDS:
                items = fetch_schedule_items(ch_id, cookies)
                schedule[ch_id] = items
                print(f"  CH {ch_id} → {len(items)} 个节目时间点")
                time.sleep(1)
            last_fetch = now_ts
            print(f"[{now_hkt_str()}] 刷新完成")

        # ── 每 30 秒检查提醒窗口 ──────────────────────────────────────────────
        now_dt = datetime.now(tz=HKT)
        hi = REMIND_MINUTES * 60
        lo = (REMIND_MINUTES - WINDOW_MINUTES) * 60

        sent_this_run: set = set()  # 跨频道去重

        for ch_id, items in schedule.items():
            for item in items:
                diff = (item["dt"] - now_dt).total_seconds()
                if not (lo < diff <= hi):
                    continue

                key = f"{ch_id}|{item['id']}"
                if key in sent:
                    continue

                detail = fetch_program_detail(item["id"], cookies)
                if not detail or not detail["title"]:
                    continue
                if not match_keywords(detail["title"]):
                    continue

                # 跨频道去重：同标题+同时间只推送一次
                dedupe_key = f"{detail['title']}|{item['dt'].timestamp()}"
                if dedupe_key in sent_this_run:
                    sent.add(key)
                    print(f"[{now_hkt_str()}] ⏭ 跨频道去重跳过：{detail['title']} (CH {ch_id})")
                    continue

                msg = build_message(ch_id, detail["title"], detail["live"], item["dt"])
                if send_telegram(msg, detail.get("image_url", "")):
                    sent.add(key)
                    sent_this_run.add(dedupe_key)
                    print(f"[{now_hkt_str()}] ✅ 已提醒：{detail['title']} (CH {ch_id})")

        time.sleep(30)


if __name__ == "__main__":
    main()
