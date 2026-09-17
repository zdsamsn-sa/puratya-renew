#!/usr/bin/env python3
"""Call notify-gateway from a renewal or backup job.

Field list, errors, and GitHub Actions wiring: docs/renew-client.md
(in the notify-gateway repo: https://github.com/2Bdou/notify-gateway)

续期仓库不再内置 SMTP / Telegram 发送，统一走 notify-gateway：
  续期结果上报给网关，网关按项目开关把通知发到邮件 + Telegram。
  仓库里只需配两个 Secret：NOTIFY_URL、NOTIFY_TOKEN。
"""

from __future__ import annotations

import json
import os
import urllib.request

NOTIFY_URL = os.environ.get("NOTIFY_URL", "http://127.0.0.1:43147/api/notify")
NOTIFY_TOKEN = os.environ.get("NOTIFY_TOKEN", "")

# 网关域挂在 Cloudflare 后，urllib 默认 UA 会被 CF 拦成 403 error 1010，
# 必须伪装成浏览器 UA。
NOTIFY_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def notify(title, content, level="success", details=None, source="puratya-renew"):
    payload = {
        "source": source,
        "title": title,
        "content": content,
        "level": level,
        "channel": ["email", "telegram"],
        "data": details or {"total": 0, "success": 0, "failed": 0, "details": []},
    }
    req = urllib.request.Request(
        NOTIFY_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer {}".format(NOTIFY_TOKEN),
            "Content-Type": "application/json",
            "User-Agent": NOTIFY_UA,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


if __name__ == "__main__":
    print(
        json.dumps(
            notify(
                "MWS 续期完成",
                "续期完成报告",
                level="partial",
                details={
                    "total": 5,
                    "success": 3,
                    "failed": 2,
                    "details": [
                        {"id": "bot_001", "name": "Bot A", "status": "success"},
                        {"id": "bot_002", "name": "Bot B", "status": "failed", "error": "HTTP 403"},
                        {"id": "site_001", "name": "Site C", "status": "partial", "message": "1/2 续期成功"},
                    ],
                },
            ),
            ensure_ascii=False,
            indent=2,
        )
    )