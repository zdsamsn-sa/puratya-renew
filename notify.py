#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用通知模块（可复用）

参考: https://github.com/alivedou/dnshe-renewal

通道（可并存，失败不抛、不阻断主流程）：
  - Telegram: TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
              或兼容 TG_BOT_TOKEN + TG_CHAT_ID
  - SMTP:     Secret SMTP_CONFIG（单个 JSON）

用法（任意项目）::

    from notify import send_notification
    send_notification("正文内容", title="标题")

环境变量见各函数文档字符串。
"""

from __future__ import annotations

import json
import os
import smtplib
import ssl
from email.header import Header
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

import requests


# ---------------------------------------------------------------------------
# SMTP
# ---------------------------------------------------------------------------

def load_smtp_config() -> Optional[Dict[str, Any]]:
    """
    读取 Secret ``SMTP_CONFIG``（单个 JSON 对象），例如::

        {
          "host": "smtp.qq.com",
          "port": 465,
          "user": "you@qq.com",
          "pass": "授权码",
          "from": "you@qq.com",
          "to": "recv@example.com",
          "ssl": true
        }

    字段：host/user/pass(或 password)/to 必填；port 默认 465；
    from 默认 = user；ssl 默认 true（465 SSL）；587 请设 ``"ssl": false``（STARTTLS）。
    to 多人用逗号分隔。
    """
    raw = (os.environ.get("SMTP_CONFIG") or "").strip()
    if not raw:
        return None
    try:
        cfg = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"SMTP_CONFIG 不是合法 JSON: {e}")
        return None
    if not isinstance(cfg, dict):
        print("SMTP_CONFIG 必须是 JSON 对象")
        return None

    host = (cfg.get("host") or "").strip()
    user = (cfg.get("user") or "").strip()
    password = (cfg.get("pass") or cfg.get("password") or "").strip()
    mail_to = (cfg.get("to") or "").strip()
    if not (host and user and password and mail_to):
        print("SMTP_CONFIG 缺 host/user/pass/to，跳过邮件")
        return None

    port_raw = cfg.get("port", 465)
    try:
        port = int(port_raw)
    except (TypeError, ValueError):
        print(f"SMTP_CONFIG.port 非法: {port_raw!r}，用 465")
        port = 465

    ssl_val = cfg.get("ssl", True)
    if isinstance(ssl_val, str):
        use_ssl = ssl_val.strip().lower() in ("1", "true", "yes", "on")
    else:
        use_ssl = bool(ssl_val)

    return {
        "host": host,
        "port": port,
        "user": user,
        "pass": password,
        "from": (cfg.get("from") or user).strip(),
        "to": mail_to,
        "ssl": use_ssl,
    }


def send_smtp(content: str, title: str = "通知") -> bool:
    """SMTP 发信。成功 True；未配置/失败 False（只打日志，不抛）。

    title 仅作邮件 Subject；正文用 content（调用方已拼好完整文案）。
    """
    cfg = load_smtp_config()
    if not cfg:
        return False

    body = content if content else (title or "通知")
    recipients = [x.strip() for x in cfg["to"].split(",") if x.strip()]
    if not recipients:
        print("SMTP_CONFIG.to 解析后为空，跳过邮件")
        return False

    subject = (title or "通知").strip() or "通知"
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = str(Header(subject, "utf-8"))
        msg["From"] = cfg["from"]
        msg["To"] = ", ".join(recipients)

        host, port = cfg["host"], cfg["port"]
        if cfg["ssl"] or port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, timeout=30, context=context) as s:
                s.login(cfg["user"], cfg["pass"])
                s.sendmail(cfg["from"], recipients, msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.ehlo()
                s.starttls(context=ssl.create_default_context())
                s.login(cfg["user"], cfg["pass"])
                s.sendmail(cfg["from"], recipients, msg.as_string())
        print("SMTP 推送成功 ->", ", ".join(recipients))
        return True
    except Exception as e:
        print("SMTP 推送失败:", str(e))
        print(f"::warning::SMTP 推送失败: {e}")
        return False


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

def _telegram_credentials() -> tuple:
    """兼容两套环境变量命名。"""
    token = (
        (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
        or (os.environ.get("TG_BOT_TOKEN") or "").strip()
    )
    chat_id = (
        (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
        or (os.environ.get("TG_CHAT_ID") or "").strip()
    )
    return token, chat_id


def _split_telegram_text(text: str, max_len: int = 4000) -> List[str]:
    """Telegram 单条上限 4096，按行尽量整段拆分。"""
    chunks: List[str] = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        cut = text.rfind("\n", 0, max_len)
        if cut < max_len // 2:
            cut = max_len
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks


def send_telegram(content: str, title: str = "") -> bool:
    """
    Telegram Bot 推送。成功至少发出一条则 True。
    环境变量：
      TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
      或 TG_BOT_TOKEN / TG_CHAT_ID

    title 可选；若正文已含标题则不再重复拼接。
    """
    token, chat_id = _telegram_credentials()
    if not token or not chat_id:
        return False

    title = (title or "").strip()
    if title and content and title not in content[:80]:
        text = f"{title}\n\n{content}"
    else:
        text = content or title
    chunks = _split_telegram_text(text)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    any_ok = False

    for i, chunk in enumerate(chunks, 1):
        if len(chunks) > 1:
            chunk = f"({i}/{len(chunks)})\n{chunk}"
        data = {
            "chat_id": chat_id,
            "text": chunk,
            "disable_web_page_preview": True,
        }
        try:
            resp = requests.post(url, json=data, timeout=15)
            print(f"Telegram 推送 [{i}/{len(chunks)}]:", resp.text[:200])
            if resp.status_code < 400:
                any_ok = True
            else:
                print("Telegram 推送失败 HTTP", resp.status_code)
                print(f"::warning::Telegram 推送失败 HTTP {resp.status_code}")
        except Exception as e:
            print("Telegram 推送失败:", str(e))
            print(f"::warning::Telegram 推送失败: {e}")
    return any_ok


# ---------------------------------------------------------------------------
# 统一入口
# ---------------------------------------------------------------------------

def send_notification(content: str, title: str = "通知") -> bool:
    """
    通知通道（可并存，互不影响）：
      - SMTP：Secret SMTP_CONFIG（JSON）
      - Telegram：TELEGRAM_* 或 TG_*
    都未配置则只打日志跳过，返回 True（视为无需推送）。
    已配置通道时：至少一个成功 → True；全部失败 → False。
    失败不抛异常，不阻断调用方；会打印 GitHub Actions ``::warning::``。
    """
    has_smtp = bool((os.environ.get("SMTP_CONFIG") or "").strip())
    token, chat_id = _telegram_credentials()
    has_tg = bool(token and chat_id)

    if not has_smtp and not has_tg:
        print("未配置 SMTP_CONFIG 或 TELEGRAM_*/TG_*，跳过推送")
        return True

    results = []
    if has_smtp:
        results.append(("SMTP", send_smtp(content, title)))
    if has_tg:
        results.append(("Telegram", send_telegram(content, title)))

    any_ok = any(ok for _, ok in results)
    if not any_ok:
        failed = ", ".join(name for name, ok in results if not ok)
        msg = f"通知推送全部失败（已尝试: {failed}）"
        print(msg)
        print(f"::warning::{msg}")
        return False

    for name, ok in results:
        if not ok:
            print(f"::warning::{name} 推送失败（其它通道已成功）")
    return True


# 别名：方便主程序写成 notify(...)
notify = send_notification


if __name__ == "__main__":
    # 本地自测：export 好变量后 python notify.py
    send_notification("这是一条测试消息。", title="notify 模块测试")
