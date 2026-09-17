# MWS 自动续期（puratya-renew）

[cloud.puratya.com](https://cloud.m-ws.cc)（MWS）的 Bot / 网站有 **7 天倒计时**，到期会自动停止。点一下 `Renew` 按钮就能把倒计时重置回 7 天。

这个项目帮你**每周一、三、五自动点续期**，让你挂在上面的 Bot / 网站永不停止，完全免费、不用自己每天登录去点。

## 原理

续期按钮背后其实就是一次请求：

```
POST /api/bots/{id}/renew     # Bot 续期
POST /api/sites/{id}/renew    # 网站续期
```

脚本每周一、三、五定时跑一次，把账号下所有 Bot / 网站全部续期，然后通过 **notify-gateway**（[2Bdou/notify-gateway](https://github.com/2Bdou/notify-gateway)）统一上报结果，网关再把通知发到你的邮件 + Telegram。

> 通知通道（SMTP / Telegram）收件人统一在网关后台配置，本仓库**不**内置、也**不**配 SMTP / Bot Token / 收件人。只需给网关上报地址和 Key。

## 用法（3 步）

### 1. Fork 本仓库

点右上角 **Fork**。

### 2. 填 Secrets

进入你的仓库 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**，填：

| Name           | 值                                   | 必填 |
| -------------- | ------------------------------------ | ---- |
| `MWS_TOKEN`    | 你的登录 token（下面教你怎么拿）       | ✅   |
| `NOTIFY_URL`   | 通知网关上报地址（以 `/api/notify` 结尾） | ✅   |
| `NOTIFY_TOKEN` | 网关里该项目分配的独立 Key           | ✅   |

> `NOTIFY_URL` / `NOTIFY_TOKEN` 在网关后台 **项目详情页** 复制（网关的部署、SMTP / Telegram 配置见 [notify-gateway](https://github.com/2Bdou/notify-gateway) 的 README）。一个续期仓库对应网关里的一个项目，各用一把 Key。
>
> 通知通道最终能不能发出去，取决于网关里该项目开关和网关设置页有没有配 SMTP / Telegram。**配好网关前也能正常续期**，只是没有通知。

### 3. 手动跑一次验证

仓库 → **Actions** → 左侧 **MWS Renew** → **Run workflow** → **Run workflow**。看到绿色 ✅ 就成功了。

## 怎么拿 MWS_TOKEN

1. 浏览器登录 [cloud.puratya.com](https://cloud.m-ws.cc)
2. 按 `F12` 打开开发者工具 → 顶部选 **Network（网络）**
3. 刷新页面（或点一下 `Renew` 按钮）
4. 点任意一个 `bots` / `renew` 请求
5. 在 **Request Headers** 里找到 `cookie:` 这一行，复制 `__Host-mrtcloud_token=` **后面那一长串**（是 `eyJ...` 开头的）
6. 粘贴进 GitHub Secret `MWS_TOKEN`

## ⚠️ Token 有效期

`MWS_TOKEN` 是个 JWT，**约 26 天后过期**。过期后脚本会检测到，向网关上报一条 `token 已失效` 的失败通知，你重新抓一次新 token 更新到 Secret 即可。

## 改运行时间

默认每周一、三、五**北京时间 09:00** 跑一次。要改，编辑 `.github/workflows/renew.yml` 里的 `cron`（注意 GitHub 用 UTC 时间，北京时间减 8 小时；5 个字段是「分 时 日 月 星期」，星期 1=周一）：

```
'0 1 * * 1,3,5'   # UTC 01:00 = 北京时间 09:00，周一三五
```

- 每天：`'0 1 * * *'`
- 每 3 天：`'0 1 */3 * *'`（月末会跳，介意就用星期枚举）

改完 commit 到默认分支生效。

## 运行文件配置

### 下载文件zsd.zip

下载压缩包之后自行改动

### ❗务必在环境变量配置DISCORD_TOKEN否则节点不通。如何配置自行找AI。❗

<img width="1404" height="599" alt="image" src="https://github.com/user-attachments/assets/24824032-9a29-4ded-9540-3d6c5455652e" />


### 出口（网络）选最后一个
<img width="1379" height="577" alt="image" src="https://github.com/user-attachments/assets/22d9b8a1-484a-4f2a-8a57-11d2d6bcb251" />

### 先手动跑一边，拿到分配的端口自行在app.py修改

<img width="1181" height="240" alt="image" src="https://github.com/user-attachments/assets/b4f99047-40a1-41c7-b813-2d25d8ed5b10" />

<img width="1125" height="98" alt="56d6ad05-8abd-43bb-8978-429daf3f9920" src="https://github.com/user-attachments/assets/6a6e2142-67a4-4f73-b793-5bca3f511a05" />


## 免责声明

本项目仅供个人使用，用于续期你自己的账号资源。请遵守 MWS 平台的服务条款，不要用于批量注册或薅羊毛。
