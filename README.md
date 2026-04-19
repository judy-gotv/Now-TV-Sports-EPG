# Now TV Sports EPG — 自动抓取 + Telegram 5分钟提醒

## 快速开始（3 步搞定）

### 第一步：安装依赖

```bash
pip install -r requirements.txt
```

### 第二步：填入你的 Telegram 配置

打开 `nowtv_reminder_auto.py`，找到顶部「配置区」，改这两行：

```python
BOT_TOKEN = "你的Bot Token"   # 从 @BotFather 获取
CHAT_ID   = "你的Chat ID"     # 从 getUpdates 获取（见下方说明）
```

其余参数保持默认即可：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| REMIND_MINUTES | 5 | 提前几分钟提醒 |
| FETCH_INTERVAL | 180 | 每 3 分钟自动抓取一次节目表 |
| CHANNEL_IDS | 全部体育频道 | CH 611/621/622/623/630/631/635/680 |
| KEYWORDS | [] | 留空=全部节目提醒；填关键词只提醒匹配节目 |

### 第三步：运行

```bash
# 前台运行（可看到日志）
python nowtv_reminder_auto.py

# 后台持续运行（Linux / Mac）
nohup python nowtv_reminder_auto.py >> nowtv.log 2>&1 &

# 查看后台日志
tail -f nowtv.log
```

---

## 如何获取 Bot Token 和 Chat ID

1. Telegram 搜索 **@BotFather** → 发送 `/newbot` → 按提示填名字 → 复制拿到的 Token
2. 给你刚创建的 bot 发任意一条消息（必须先发消息才能拿到 chat_id）
3. 浏览器访问：

```
https://api.telegram.org/bot<你的TOKEN>/getUpdates
```

4. 在返回的 JSON 里找到：

```json
"chat": { "id": 123456789 }
```

这个数字就是你的 `CHAT_ID`

---

## 关键词过滤（可选）

只想提醒特定节目类型，在脚本里改 `KEYWORDS`，留空则全部节目都提醒：

```python
# 只提醒英超、斯诺克、羽毛球
KEYWORDS = ["PL Goals", "Premier League", "Century Break", "Badminton"]

# 只提醒直播
KEYWORDS = ["Live", "直播"]

# 全部节目（默认）
KEYWORDS = []
```

---

## 脚本工作原理

```
启动
  ↓
发送 TG 心跳消息（确认 bot 正常）
  ↓
循环：
  每 3 分钟 → 抓取 nowplayer.now.com 各频道节目表
  每 30 秒  → 检查时间窗口
              命中「距开播 4~5 分钟」→ 推送 TG 提醒
              每个节目只提醒一次，不重复
  抓取失败  → 自动使用内置备用节目表，不中断
```

监控频道：

| 频道号 | 名称 |
|--------|------|
| CH 611 | Now Sports 4K 1 |
| CH 621 | Now Sports Premier League 1 |
| CH 622 | Now Sports Premier League 2 |
| CH 623 | Now Sports Premier League 3 |
| CH 630 | Now Sports Prime（PL Goals / Century Break / Badminton Unlimited 等）|
| CH 631 | Now Sports Prime 2 |
| CH 635 | Now Sports 5（女子足球等）|
| CH 680 | Now Sports Plus |

---

## TG 提醒消息样式

```
🔴 Now TV Sports · 开播前 5 分钟提醒

🎯 Premier League 25/26 - Man City vs Arsenal
📡 频道：CH 621 Premier League 1
🕐 时间：04/19（日）23:00 HKT
⚡ 状态：直播即将开始 🔥

🔗 打开节目表
```

---

## 常见问题

**Q：运行后没有收到 TG 消息？**
- 检查 BOT_TOKEN 和 CHAT_ID 是否填写正确
- 确保你已经先给 bot 发过一条消息
- 检查网络是否能访问 api.telegram.org

**Q：抓取节目表失败怎么办？**
- 脚本会自动切换到内置备用节目表，不会中断提醒
- 备用表包含常见节目如 PL Goals、Century Break、Premier League 直播等

**Q：如何停止后台运行的脚本？**
```bash
# 找到进程号
ps aux | grep nowtv_reminder_auto

# 终止进程
kill <进程号>
```

**Q：如何在 Windows 上后台运行？**
```bash
# 使用 start 命令后台运行
start /B python nowtv_reminder_auto.py > nowtv.log 2>&1
```
