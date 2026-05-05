// ── 配置区 ────────────────────────────────────────────────────────────────────
const CHANNEL_IDS = [
  "611", "612",
  "621", "622", "623",
  "630", "631", "632", "633", "634", "635", "636", "637", "638", "639",
  "640", "641", "643",
  "647",
  "668",
  "680",
  "683", "684",
];
const CHANNEL_NAMES = {
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
};
const REMIND_MINUTES = 5;   // 提前几分钟提醒
const WINDOW_MINUTES = 3;   // 提醒窗口宽度（分钟），建议 >= Cron 间隔
const BASE_URL = "https://nowplayer.now.com";
const FETCH_HEADERS = {
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
  "Accept-Language": "zh-HK,zh;q=0.9,en;q=0.8",
  "Accept-Encoding": "gzip, deflate, br",
  "Upgrade-Insecure-Requests": "1",
  "Sec-Fetch-Dest": "document",
  "Sec-Fetch-Mode": "navigate",
  "Sec-Fetch-Site": "none",
  "Cache-Control": "max-age=0",
};
// 关键词过滤（留空 = 全部节目；填关键词只提醒匹配的）
const KEYWORDS = [];
// ─────────────────────────────────────────────────────────────────────────────

// ── 12小时制时间解析 ──────────────────────────────────────────────────────────
function parse12HourTime(timeStr, dateStr) {
  const m = timeStr.match(/^(\d{1,2}):(\d{2})(AM|PM)$/i);
  if (!m) return null;
  let h = parseInt(m[1], 10);
  const min = parseInt(m[2], 10);
  const ampm = m[3].toUpperCase();
  if (ampm === "AM" && h === 12) h = 0;
  if (ampm === "PM" && h !== 12) h += 12;
  return new Date(`${dateStr}T${String(h).padStart(2, "0")}:${String(min).padStart(2, "0")}:00+08:00`);
}

// ── 获取 Session Cookie ───────────────────────────────────────────────────────
async function getSessionCookie() {
  try {
    const resp = await fetch(`${BASE_URL}/tvguide`, { headers: FETCH_HEADERS, redirect: "follow" });
    const raw = resp.headers.get("set-cookie") || "";
    // 只提取 name=value，跳过 Max-Age/Domain/Path 等指令
    const cookies = [...raw.matchAll(/\b(NOWSESSIONID|NOW_SESSION|LANG)=([^;,\s]*)/g)]
      .map(m => `${m[1]}=${m[2]}`)
      .join("; ");
    console.log(`Session cookie 获取成功: ${cookies.slice(0, 80)}`);
    return cookies;
  } catch (e) {
    console.warn(`获取 session cookie 失败: ${e}`);
    return "";
  }
}

// ── 从频道页面提取 <li> 的 ID + 时间（不需要节目名）────────────────────────────
async function fetchScheduleItems(channelId, cookie) {
  const items = []; // [{id, timeStr, dt, dateStr}]
  const headers = cookie ? { ...FETCH_HEADERS, Cookie: cookie } : FETCH_HEADERS;

  const nowHkt = new Date(Date.now() + 8 * 3600_000);
  const currentMonth = nowHkt.getUTCMonth();
  const currentDay = nowHkt.getUTCDate();
  const currentYear = nowHkt.getUTCFullYear();

  for (let week = 0; week <= 0; week++) {
    const url = `${BASE_URL}/tvguide/channeldetail/${channelId}/${week}`;
    try {
      const resp = await fetch(url, { headers });
      if (!resp.ok) continue;
      const html = await resp.text();

      // 提取周标签日期：id="week1" → day number
      const weekDates = {};
      for (const m of html.matchAll(/id="week(\d+)"[\s\S]{1,400}?<br>(\d+)<\/div>/g)) {
        const weekNum = parseInt(m[1]);
        const d = parseInt(m[2]);
        let month = currentMonth;
        if (d < currentDay - 20) month = (currentMonth + 1) % 12;
        if (d > currentDay + 20) month = (currentMonth - 1 + 12) % 12;
        const year = month === 0 && currentMonth === 11 ? currentYear + 1 : currentYear;
        weekDates[weekNum] = `${year}-${String(month + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
      }

      // 按日期区块分割
      const parts = html.split(/<div\s+id="day(\d+)"\s+class="all-data-day[^>]*"[^>]*>/);
      for (let i = 1; i < parts.length; i += 2) {
        const dayNum = parseInt(parts[i]);
        const dayContent = parts[i + 1] || "";
        const dateStr = weekDates[dayNum];
        if (!dateStr) continue;

        // 提取每个 <li>：id、时间、封面图
        for (const liMatch of dayContent.matchAll(/<li\s+id="(\d+)"[^>]*>([\s\S]*?)<\/li>/g)) {
          const liId = liMatch[1];
          const liContent = liMatch[2];
          const timeM = liContent.match(/<div[^>]*class="time"[^>]*>(\d{1,2}:\d{2}(?:AM|PM))<\/div>/i);
          if (!timeM) continue;
          const dt = parse12HourTime(timeM[1], dateStr);
          if (dt) items.push({ id: liId, timeStr: timeM[1], dt, dateStr });
        }
      }
    } catch (e) {
      console.warn(`CH ${channelId} week=${week}: ${e}`);
    }
  }
  return items;
}

// ── 调用详情 API 获取节目名 ───────────────────────────────────────────────────
async function fetchProgramDetail(programId, cookie) {
  const url = `${BASE_URL}/tvguide/epgprogramdetail?programId=${programId}`;
  const headers = { ...FETCH_HEADERS, Cookie: cookie, "X-Requested-With": "XMLHttpRequest" };
  try {
    const resp = await fetch(url, { headers });
    if (!resp.ok) return null;
    const data = await resp.json();
    // 字段名从 jQuery 代码推断：chiSeriesName / chiProgName / isLive
    const seriesName = (data.chiSeriesName || data.engSeriesName || "").trim();
    const progName = (data.chiProgName || data.engProgName || "").trim();
    let title;
    if (!progName) {
      title = seriesName;
    } else if (seriesName && !progName.startsWith(seriesName)) {
      title = `${seriesName} ${progName}`.trim();
    } else {
      title = progName;
    }
    const isLive = data.isLive === "Y" || data.isLive === true;
    if (!title || title.startsWith("请留意") || title.startsWith("請留意")) return null;
    console.log(`Program ${programId}: "${title}", isLive=${isLive}`);
    return { title, isLive };
  } catch (e) {
    console.warn(`Program detail ${programId}: ${e}`);
    return null;
  }
}

// ── 关键词匹配 ────────────────────────────────────────────────────────────────
function matchKeywords(title) {
  if (!KEYWORDS.length) return true;
  const tl = title.toLowerCase();
  return KEYWORDS.some((kw) => tl.includes(kw.toLowerCase()));
}

// ── 频道运动图标 ──────────────────────────────────────────────────────────────
function getSportEmoji(ch) {
  const map = {
    "611": "⚽", "612": "🏎️",
    "621": "⚽", "622": "⚽", "623": "⚽",
    "630": "🏅", "631": "🏅",
    "632": "⚽", "633": "⚽",
    "634": "🎾", "635": "🏅", "636": "🎾",
    "637": "🎱", "638": "🏅", "639": "🏅",
    "640": "⚽", "641": "🏀", "643": "🏎️",
    "647": "🏍️", "668": "🐴", "680": "🏅",
    "683": "⛳", "684": "⛳",
  };
  return map[ch] || "📺";
}

// ── 消息构建 ──────────────────────────────────────────────────────────────────
function buildMessage(p) {
  const liveIcon = p.live ? "🔴" : "📺";
  const liveText = p.live ? "直播即将开始 🔥" : "即将播出";
  const sportEmoji = getSportEmoji(p.ch);
  const hkt = new Date(p.dt.getTime() + 8 * 3600_000);
  const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const mm = String(hkt.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(hkt.getUTCDate()).padStart(2, "0");
  const dow = days[hkt.getUTCDay()];
  const hh = String(hkt.getUTCHours()).padStart(2, "0");
  const mi = String(hkt.getUTCMinutes()).padStart(2, "0");
  const tStr = `${mm}/${dd}（${dow}）${hh}:${mi} HKT`;
  const chLabel = CHANNEL_NAMES[p.ch] ?? `CH ${p.ch}`;
  return (
    `${liveIcon} <b>${liveText}</b>\n` +
    `━━━━━━━━━━━━━━━\n` +
    `${sportEmoji} <b>${p.title}</b>\n` +
    `━━━━━━━━━━━━━━━\n` +
    `📡 CH ${p.ch} · ${chLabel}\n` +
    `🕐 ${tStr}\n\n` +
    `<i>Now TV Sports · 开播前 ${REMIND_MINUTES} 分钟提醒</i>`
  );
}

// ── Telegram 发送（返回 {ok, messages:[{chatId,messageId}]}）────────────────
async function sendTelegram(env, text) {
  const chatIds = env.CHAT_ID.split(",").map(s => s.trim()).filter(Boolean);
  let allOk = true;
  const messages = [];
  for (const chatId of chatIds) {
    try {
      const resp = await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendMessage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chat_id: chatId, text, parse_mode: "HTML" }),
      });
      if (resp.ok) {
        const json = await resp.json();
        const messageId = json.result?.message_id;
        console.log(`TG发送成功 chat=${chatId} msg=${messageId}`);
        if (messageId) messages.push({ chatId, messageId });
      } else {
        console.error(`TG失败 chat=${chatId} ${resp.status}: ${await resp.text()}`);
        allOk = false;
      }
    } catch (e) {
      console.error(`TG网络错误 chat=${chatId}: ${e}`);
      allOk = false;
    }
  }
  return { ok: allOk, messages };
}

// ── 删除 Telegram 消息，返回是否成功 ─────────────────────────────────────────
async function deleteTelegramMessage(env, chatId, messageId) {
  try {
    const resp = await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/deleteMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, message_id: messageId }),
    });
    const json = await resp.json();
    if (resp.ok && json.result === true) {
      console.log(`🗑 群内消息已删除 msg=${messageId} chat=${chatId}`);
      return true;
    }
    // 消息不存在（已被手动删除）也视为成功
    if (json.description && json.description.includes("message to delete not found")) {
      console.log(`🗑 消息已不存在，跳过 msg=${messageId}`);
      return true;
    }
    console.error(`❌ 群内消息删除失败 msg=${messageId} chat=${chatId} status=${resp.status} err=${JSON.stringify(json)}`);
    return false;
  } catch (e) {
    console.error(`❌ 删除消息网络错误 msg=${messageId}: ${e}`);
    return false;
  }
}

// ── 主逻辑 ───────────────────────────────────────────────────────────────────
async function runCheck(env) {
  const nowSec = Math.floor(Date.now() / 1000);

  // ── 步骤1：处理到期删除任务 ──────────────────────────────────────────────────
  try {
    const pending = await env.SENT_KV.list({ prefix: "del:" });
    for (const { name } of pending.keys) {
      const val = await env.SENT_KV.get(name, { type: "json" });
      if (!val) { await env.SENT_KV.delete(name); continue; }
      if (nowSec >= val.deleteAt) {
        const ok = await deleteTelegramMessage(env, val.chatId, val.messageId);
        if (ok) await env.SENT_KV.delete(name);
      }
    }
  } catch (e) {
    console.warn(`删除队列处理失败: ${e}`);
  }

  // ── 步骤2：抓取节目表并推送提醒 ──────────────────────────────────────────────
  const cookie = await getSessionCookie();
  const nowMs = Date.now();
  const hiMs = REMIND_MINUTES * 60_000;
  const loMs = (REMIND_MINUTES - WINDOW_MINUTES) * 60_000;
  const DELETE_AFTER_SEC = 5 * 60;

  const sentThisRun = new Set();

  for (const chId of CHANNEL_IDS) {
    const items = await fetchScheduleItems(chId, cookie);
    console.log(`CH ${chId}: 共 ${items.length} 个节目时间点`);

    const upcoming = items.filter(p => {
      const diff = p.dt.getTime() - nowMs;
      return diff > loMs && diff <= hiMs;
    });

    for (const item of upcoming) {
      if (sentThisRun.has(item.id)) continue;

      const key = `${chId}|${item.id}`;
      const alreadySent = await env.SENT_KV.get(key);
      if (alreadySent) continue;

      const detail = await fetchProgramDetail(item.id, cookie);
      if (!detail || !detail.title) continue;
      if (!matchKeywords(detail.title)) continue;

      const dedupeKey = `${detail.title}|${item.dt.getTime()}`;
      if (sentThisRun.has(dedupeKey)) {
        await env.SENT_KV.put(key, "1", { expirationTtl: 86400 });
        console.log(`⏭ 去重跳过：${detail.title} (CH ${chId})`);
        continue;
      }

      const prog = { ch: chId, title: detail.title, live: detail.isLive, dt: item.dt };
      const result = await sendTelegram(env, buildMessage(prog));
      console.log(`sendTelegram结果: ok=${result.ok} 成功发送=${result.messages.length}个`);
      if (result.messages.length > 0) {
        await env.SENT_KV.put(key, "1", { expirationTtl: 86400 });
        sentThisRun.add(item.id);
        sentThisRun.add(dedupeKey);
        console.log(`✅ 已提醒：${detail.title} (CH ${chId})`);
        const deleteAt = nowSec + DELETE_AFTER_SEC;
        for (const { chatId, messageId } of result.messages) {
          const delKey = `del:${chatId}_${messageId}`;
          await env.SENT_KV.put(delKey, JSON.stringify({ chatId, messageId, deleteAt }), { expirationTtl: 3600 });
          console.log(`🕐 登记删除 msg=${messageId} at=${deleteAt}`);
        }
      }
    }
  }
}

// ── Worker 入口 ───────────────────────────────────────────────────────────────
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.searchParams.get("test") === "1") {
      ctx.waitUntil(runCheck(env, ctx));
      return new Response("触发成功，请查看 Telegram 和日志", { status: 200 });
    }
    // 清空所有 KV 记录（sent + del），用法：?flush=1
    if (url.searchParams.get("flush") === "1") {
      let cursor, count = 0;
      do {
        const list = await env.SENT_KV.list({ cursor });
        for (const { name } of list.keys) {
          await env.SENT_KV.delete(name);
          count++;
        }
        cursor = list.list_complete ? undefined : list.cursor;
      } while (cursor);
      return new Response(`✅ 已清空 KV，共删除 ${count} 条记录`, { status: 200 });
    }
    // 调试：查看任意节目的原始 API 数据，用法：?debug=节目ID
    const debugId = url.searchParams.get("debug");
    if (debugId) {
      const cookie = await getSessionCookie();
      const apiUrl = `${BASE_URL}/tvguide/epgprogramdetail?programId=${debugId}`;
      const headers = { ...FETCH_HEADERS, Cookie: cookie, "X-Requested-With": "XMLHttpRequest" };
      const resp = await fetch(apiUrl, { headers });
      const data = await resp.json();
      return new Response(JSON.stringify(data, null, 2), {
        headers: { "Content-Type": "application/json; charset=utf-8" },
      });
    }
    return new Response("Now TV Sports EPG Worker running.", { status: 200 });
  },

  async scheduled(_event, env, ctx) {
    ctx.waitUntil(runCheck(env, ctx));
  },
};
