# 通知说明（notify-gateway）

本仓库的通知**不**再自己发邮件 / Telegram，统一走 **notify-gateway**（[2Bdou/notify-gateway](https://github.com/2Bdou/notify-gateway)）。

续期脚本把结构化结果（`level` + 每个 Bot / Site 的明细 `details`）上报给网关，网关按项目开关把通知发到邮件 + Telegram。收件人和 Bot 统一在网关设置页配，本仓库**只配两个 Secret**：

| Secret          | 说明 |
| --------------- | ---- |
| `NOTIFY_URL`    | 网关上报地址，完整路径以 `/api/notify` 结尾 |
| `NOTIFY_TOKEN`  | 网关里对应本项目分配的独立 Key（Bearer 鉴权） |

## 怎么配（前置：网关先上线）

1. 把 [notify-gateway](https://github.com/2Bdou/notify-gateway) 部署到 Cloudflare，按它的 README 完成初始化。
2. 网关 **设置** 页配好 SMTP / Telegram（发信通道统一在这配一次）。
3. 网关后台 **新建项目**，名称和本仓库一致（例如 `puratya-renew`），创建后复制详情页的 `NOTIFY_URL` 和 `NOTIFY_TOKEN`。
4. 这两个值分别填进本仓库的 GitHub Secret `NOTIFY_URL` / `NOTIFY_TOKEN`。

> 网关没配 SMTP / Telegram 时，上报仍会成功（通道返回 `mock_*` messageId），任务也会进网关后台，只是不会真发信。续期本身不受影响。

## 本仓库怎么上报

脚本 `renew.py` 在三种情况下上报：

- **token 失效**：`level="failed"`，提醒你更新 `MWS_TOKEN`。
- **账号下没有对象**：`level="success"`，正文说明跳过。
- **正常续期**：按结果设 `level`——全部成功 `success`，有失败 `partial`；`data` 带 `total / success / failed`，`details` 里每个对象一条 `{id, name, status, error/message}`。

上报失败只打 `::warning::` 日志，**不阻断续期主流程**。上报接口的完整字段和错误码见 [notify-gateway/docs/renew-client.md](https://github.com/2Bdou/notify-gateway/blob/main/docs/renew-client.md)。