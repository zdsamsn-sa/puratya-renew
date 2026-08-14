# MWS 自动续期（puratya-renew）

[cloud.puratya.com](https://cloud.puratya.com)（MWS）的 Bot / 网站有 **7 天倒计时**，到期会自动停止。点一下 `Renew` 按钮就能把倒计时重置回 7 天。

这个项目帮你**每周一、三、五自动点续期**，让你挂在上面的 Bot / 网站永不停止，完全免费、不用自己每天登录去点。

## 原理

续期按钮背后其实就是一次请求：

```
POST /api/bots/{id}/renew     # Bot 续期
POST /api/sites/{id}/renew    # 网站续期
```

脚本每周一、三、五定时跑一次，把账号下所有 Bot / 网站全部续期，然后通过 `notify.py`（Telegram + SMTP 双通道）通知你结果。

## 用法（3 步）

### 1. Fork 本仓库

点右上角 **Fork**。

### 2. 填 Secrets

进入你的仓库 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**，填：

| Name                  | 值                                                                                   | 必填 |
| --------------------- | ------------------------------------------------------------------------------------ | ---- |
| `MWS_TOKEN`           | 你的登录 token（下面教你怎么拿）                                                       | ✅   |
| `TELEGRAM_BOT_TOKEN`  | Telegram Bot token（找 [@BotFather](https://t.me/BotFather) `/newbot`）               | 可选 |
| `TELEGRAM_CHAT_ID`    | Telegram 你的 ID（找 [@userinfobot](https://t.me/userinfobot)）                        | 可选 |
| `SMTP_CONFIG`         | 邮件通知，一个 JSON（见 [NOTIFY.md](NOTIFY.md)）                                       | 可选 |

> 通知是**双通道平行**：TG 和邮件都配了就都发，配哪个用哪个，一个不配不影响另一个；都不配也能正常续期，只是没通知。详细配置（含 SMTP JSON 格式、TG 兼容命名 `TG_BOT_TOKEN`/`TG_CHAT_ID`）见 [NOTIFY.md](NOTIFY.md)。

### 3. 手动跑一次验证

仓库 → **Actions** → 左侧 **MWS Renew** → **Run workflow** → **Run workflow**。看到绿色 ✅ 就成功了。

## 怎么拿 MWS_TOKEN

1. 浏览器登录 [cloud.puratya.com](https://cloud.puratya.com)
2. 按 `F12` 打开开发者工具 → 顶部选 **Network（网络）**
3. 刷新页面（或点一下 `Renew` 按钮）
4. 点任意一个 `bots` / `renew` 请求
5. 在 **Request Headers** 里找到 `cookie:` 这一行，复制 `__Host-mrtcloud_token=` **后面那一长串**（是 `eyJ...` 开头的）
6. 粘贴进 GitHub Secret `MWS_TOKEN`

## ⚠️ Token 有效期

`MWS_TOKEN` 是个 JWT，**约 26 天后过期**。过期后脚本会检测到并给你发通知（如果配了通知），你重新抓一次新 token 更新到 Secret 即可。不配通知的话，记得每 3~4 周自己来换一次。

## 改运行时间

默认每周一、三、五**北京时间 09:00** 跑一次。要改，编辑 `.github/workflows/renew.yml` 里的 `cron`（注意 GitHub 用 UTC 时间，北京时间减 8 小时；5 个字段是「分 时 日 月 星期」，星期 1=周一）：

```
'0 1 * * 1,3,5'   # UTC 01:00 = 北京时间 09:00，周一三五
```

- 每天：`'0 1 * * *'`
- 每 3 天：`'0 1 */3 * *'`（月末会跳，介意就用星期枚举）

改完 commit 到默认分支生效。

## 免责声明

本项目仅供个人使用，用于续期你自己的账号资源。请遵守 MWS 平台的服务条款，不要用于批量注册或薅羊毛。
