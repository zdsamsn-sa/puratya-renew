### 🚀 MWS 自动续期与唤醒 (Auto Renew & Wakeup)

这是一个基于 Python Playwright 与 GitHub Actions 的全自动化维护脚本，专为 MWS (cloud.puratya.com) 平台打造。它能够自动检测实例状态，执行续期，并在发现离线时强制开机，最后将直观的图文报告推送到您的 Telegram。

---

### ✨ 核心特性

* **双重执行保障**：结合网页 UI 模拟点击与底层 API 强制发包，大幅提高续期和唤醒的成功率。
* **智能离线唤醒**：精准识别 `offline`、`stopped` 等挂机状态，自动点击开机按钮或发送 Start 指令。
* **可视化图文报告**：通过 Telegram 推送执行概况，包含续期时间变化、在线状态对比以及控制面板的最新全屏截图。
* **强力纯净运行**：内置临时文件清理与 Playwright 僵尸进程防范机制，避免资源泄漏。
* **云端日志瘦身**：引入 Actions 自动化清理机制，每天自动清理 7 天前的工作流运行记录，保持仓库高度整洁。

---

### 🛠️ 环境变量配置

要让脚本正常运行，您需要在 GitHub 仓库中配置以下 Secret 变量。进入仓库的 **Settings** -> **Secrets and variables** -> **Actions** -> **Repository secrets** 依次添加：

| 变量名 | 是否必须 | 获取途径与说明 |
| --- | --- | --- |
| **`MWS_TOKEN`** | ✅ 必须 | 登录 MWS 面板，按 `F12` 打开开发者工具，在网络或存储 (Cookies) 中找到 `__Host-mrtcloud_token`，复制其完整的 JWT 值（通常以 `eyJ` 开头）。 |
| **`TG_BOT_TOKEN`** | ✅ 必须 | 在 Telegram 中向 `@BotFather` 申请创建机器人后获取的 API Token。 |
| **`TG_CHAT_ID`** | ✅ 必须 | 您的 Telegram 账号 ID，可向 `@userinfobot` 或类似机器人发送消息获取。 |

---

### 🚀 快速部署指南

1. **Fork 本仓库**：点击页面右上角的 `Fork` 按钮，将项目复制到您的个人 GitHub 账号下。
2. **配置 Secrets**：按照上方表格的要求，将三个必备的环境变量填入仓库配置中。
3. **启用工作流**：进入您仓库的 `Actions` 选项卡，点击绿色的 `I understand my workflows, go ahead and enable them` 按钮允许 Actions 运行。
4. **手动测试运行**：在 Actions 左侧边栏点击 **🚀 MWS 自动续期与离线唤醒**，随后点击右侧的 **Run workflow** 进行首次测试。
5. **等待自动执行**：脚本已配置为每天北京时间上午 09:00 (UTC 01:00) 自动在云端执行一次。

---

### 📂 项目文件结构

* **`renew.py`**：核心自动化执行脚本，负责浏览器模拟、数据抓取、状态验证及图文生成。
* **`notify.py`**：基础通知模块（如需要兼容其他推送渠道可在此扩展）。
* **`.github/workflows/renew.yml`**：GitHub Actions 配置文件，定义了运行环境、触发时间、执行步骤及旧日志清理逻辑。

---
## 怎么拿 MWS_TOKEN

1. 浏览器登录 [cloud.puratya.com](https://cloud.puratya.com)
2. 安装浏览器扩展（任选一个）：
   Cookie-Editor
   或 EditThisCookie
3. 登录成功后，点击扩展 → Export → 选择 JSON 格式
4. 把导出的内容完整复制粘贴进 GitHub Secret `MWS_TOKEN`

## ⚠️ Token 有效期

`MWS_TOKEN` 是个 JWT，**约 26 天后过期**。过期后脚本会检测到并给你发通知（如果配了通知），你重新抓一次新 token 更新到 Secret 即可。不配通知的话，记得每 3~4 周自己来换一次。


### ⚠️ 免责声明

> 本项目仅供学习与自动化运维技术交流使用。请合理设置定时执行频率，避免对目标平台服务器造成恶意高并发压力。因使用本脚本导致的任何账号异常或服务封禁，使用者需自行承担责任。
