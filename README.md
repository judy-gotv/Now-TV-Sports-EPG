# Now TV Sports EPG — 自动抓取 + Telegram 5分钟提醒

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 编辑脚本，填入 Token 和 Chat ID
# 找到脚本顶部"配置区"，改两行：
#   BOT_TOKEN = "YOUR_BOT_TOKEN"
#   CHAT_ID   = "YOUR_CHAT_ID"

# 3. 运行
python nowtv_reminder_auto.py
```

## 配置参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| BOT_TOKEN | YOUR_BOT_TOKEN | @BotFather 获取 |
| CHAT_ID | YOUR_CHAT_ID | 你的 Telegram chat_id |
| REMIND_MINUTES | 5 | 提前几分钟提醒 |
| FETCH_INTERVAL | 180 | 抓取间隔（秒），3分钟 |
| CHANNEL_IDS | 全部体育频道 | 要监控的频道号 |
| KEYWORDS | [] | 空=全部节目；填词只提醒匹配节目 |

## 如何获取 Bot Token 和 Chat ID

1. Telegram 搜索 **@BotFather** → `/newbot` → 复制 Token
2. 给你的 bot 发任意一条消息
3. 访问 `https://api.telegram.org/bot<TOKEN>/getUpdates`
4. 找到 `"chat": {"id": 123456}` 即为你的 CHAT_ID

## 关键词过滤示例

只提醒英超和斯诺克：
```python
KEYWORDS = ["PL Goals", "Premier League", "Century Break"]
```

只提醒直播：
```python
KEYWORDS = ["Live", "直播"]
```

## 后台持续运行

```bash
# Linux / Mac
nohup python nowtv_reminder_auto.py >> nowtv.log 2>&1 &

# 查看日志
tail -f nowtv.log
```

## 抓取逻辑说明

- 每 3 分钟抓取一次 nowplayer.now.com 频道详情页
- 每 30 秒检查一次时间窗口
- 命中"距开播 4~5 分钟"时发送 TG 提醒
- 每个节目只提醒一次（防重复）
- 抓取失败自动使用内置备用节目表
