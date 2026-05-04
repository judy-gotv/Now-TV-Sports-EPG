# Now TV Sports EPG — Telegram 开播提醒

自动抓取 Now TV Sports 节目表，在节目开播前 5 分钟通过 Telegram 推送提醒。支持多个群组/用户同时推送。

## 功能

- 每 3 分钟自动刷新节目时间表
- 监控 15 个 Now TV 体育频道
- 开播前 5 分钟推送 Telegram 通知
- 支持同时推送多个群组或用户
- 支持关键词过滤（只提醒指定节目）
- 用 KV 存储已发送记录，不会重复推送

## 监控频道

| 频道 ID | 名称 | 主要内容 |
|--------|------|---------|
| 611 | Now Sports 4K 1 | 英超 4K |
| 612 | Now Sports 4K 2 | F1 赛车 4K |
| 621 | Premier League 1 | 英超 |
| 622 | Premier League 2 | 英超 |
| 623 | Premier League 3 | 英超 |
| 630 | Now Sports Prime | 综合体育 |
| 631 | Now Sports Prime 2 | 综合体育 |
| 632 | Now Sports 2 | 西甲 |
| 633 | Now Sports 3 | 西甲 / FA Cup |
| 634 | Now Sports 4 | WTA 网球 |
| 635 | Now Sports 5 | 综合体育 |
| 636 | Now Sports 6 | ATP 网球 |
| 640 | MUTV | 曼联专属 |
| 641 | NBA | NBA 篮球 |
| 680 | Now Sports Plus | 综合体育 |

---

## 方案一：Cloudflare Workers（推荐，免费无需服务器）

### 第一步：创建 KV 命名空间

1. 登录 [dash.cloudflare.com](https://dash.cloudflare.com)
2. 左侧菜单 → **Workers & Pages** → **KV**
3. 点 **+ Create Instance**，名称填 `NOWTV_SENT`

### 第二步：创建 Worker 并粘贴代码

1. **Workers & Pages** → **Create** → **Create Worker**
2. 名称填 `nowtv-sports-epg`，点 **Deploy**
3. 部署后点 **编辑代码**，删掉默认代码
4. 将 `worker.js` 全部内容粘贴进去，点 **Deploy**

### 第三步：绑定 KV 与配置变量

进入 Worker → **绑定** 选项卡 → **添加绑定**：

| 类型 | 变量名 | 值 |
|------|--------|-----|
| KV 命名空间 | `SENT_KV` | `NOWTV_SENT` |

进入 Worker → **设置** → **变量和机密** → **添加**：

| 变量名 | 值 |
|--------|-----|
| `BOT_TOKEN` | 你的 Telegram Bot Token |
| `CHAT_ID` | 推送目标（多个用逗号分隔，例如 `123456,-1001234567890`）|

### 第四步：设置定时触发

进入 Worker → **设置** → **触发事件** → **添加 Cron 触发器**：

```
*/3 * * * *
```

---

## 方案二：Python 本地运行

### 安装依赖

```bash
pip install requests
```

### 配置

编辑 `nowtv_reminder_auto.py` 顶部：

```python
BOT_TOKEN = "你的Bot Token"
CHAT_ID   = ["你的Chat ID"]              # 多个目标：["123456", "-1009999999"]
```

### 运行

```bash
python nowtv_reminder_auto.py
```

---

## 获取 Telegram 信息

**Bot Token**：向 [@BotFather](https://t.me/BotFather) 发送 `/newbot` 创建机器人

**个人 Chat ID**：向 [@userinfobot](https://t.me/userinfobot) 发送任意消息即可获取

**群组 Chat ID**：将 Bot 加入群组后，访问以下链接，找 `"chat":{"id":` 后面的负数：
```
https://api.telegram.org/bot你的BOT_TOKEN/getUpdates
```

---

## 自定义配置

### Workers 版（`worker.js` 顶部）

```js
const REMIND_MINUTES = 5;    // 提前几分钟提醒
const WINDOW_MINUTES = 3;    // 提醒窗口宽度，建议 >= Cron 间隔

// 关键词过滤（留空 = 全部节目）
const KEYWORDS = [];
// 示例：const KEYWORDS = ["Premier League", "直播", "NBA", "F1"];

// 监控的频道 ID（可自行增删）
const CHANNEL_IDS = ["611", "612", "621", ...];
```

### Python 版（`nowtv_reminder_auto.py` 顶部）

```python
REMIND_MINUTES = 5           # 提前几分钟提醒
WINDOW_MINUTES = 3           # 提醒窗口宽度
FETCH_INTERVAL = 180         # 刷新间隔（秒）
KEYWORDS       = []          # 关键词过滤
```

---

## 通知格式示例

```
🔴 Now TV Sports · 开播前 5 分钟提醒

🎯 英格蘭超級聯賽 -曼聯 對 利物浦
📡 频道：CH 621 Premier League 1
🕐 时间：05/03（Sun）22:00 HKT
⚡ 状态：直播即将开始 🔥
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `worker.js` | Cloudflare Workers 部署文件 |
| `nowtv_reminder_auto.py` | Python 本地运行版本 |
