# 通用通知模块 `notify.py`

设计参考：[alivedou/dnshe-renewal](https://github.com/alivedou/dnshe-renewal)  
目标：与业务解耦，**任意续期/巡检脚本**复制 `notify.py` 即可复用。

## 架构

```
renew.py                      ← 只负责拼业务文案
        │
        ▼
notify.py                     ← 只负责推送
  ├─ send_telegram()          TG
  ├─ send_smtp()              邮件
  └─ send_notification()      统一入口（可并存）
```

## 主程序怎么调用

```python
from notify import send_notification

# 最简单（title = 邮件 Subject；正文单独传）
send_notification("续期成功\n到期：2026-08-01", title="MWS 续期通知")

# 返回 bool：已配置通道且全部失败时为 False（并打印 ::warning::）
ok = send_notification("正文", title="MWS 续期通知")
```

## Secrets（GitHub Actions）

### Telegram（任选一套命名）

| Secret | 兼容名 |
|--------|--------|
| `TELEGRAM_BOT_TOKEN` | `TG_BOT_TOKEN` |
| `TELEGRAM_CHAT_ID` | `TG_CHAT_ID` |

### SMTP（与 dnshe-renewal 相同）

Secret 名：`SMTP_CONFIG`，值为 **一个 JSON**：

```json
{
  "host": "smtp.qq.com",
  "port": 465,
  "user": "你的邮箱@qq.com",
  "pass": "授权码",
  "from": "你的邮箱@qq.com",
  "to": "接收邮箱@example.com",
  "ssl": true
}
```

- 465 + `ssl: true`（QQ/163 常用）  
- 587 + `ssl: false`（Gmail STARTTLS 常用）  
- `to` 多人：`a@x.com,b@y.com`  
- **TG 与 SMTP 可同时开**；都未配则跳过推送，不阻断主流程  

### Workflow 需传入

```yaml
env:
  TG_BOT_TOKEN: ${{ secrets.TG_BOT_TOKEN }}
  TG_CHAT_ID: ${{ secrets.TG_CHAT_ID }}
  TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
  TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
  SMTP_CONFIG: ${{ secrets.SMTP_CONFIG }}
```

## 拷到其它项目

1. 复制 `notify.py`  
2. `pip install requests`（标准库自带 smtplib）  
3. 主文件 `from notify import send_notification`  
4. Actions Secrets + workflow env 按上表配置  

## 本地试推

```bash
export TG_BOT_TOKEN='...'
export TG_CHAT_ID='...'
# 或
export SMTP_CONFIG='{"host":"smtp.qq.com","port":465,"user":"...","pass":"...","from":"...","to":"...","ssl":true}'

python notify.py
```
