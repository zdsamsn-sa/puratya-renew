#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MWS (cloud.puratya.com) 自动续期脚本

原理：MWS 的 Bot/Site 有 7 天倒计时，到期自动停止。
     点一次 Renew 按钮 = POST /api/bots/{id}/renew，把倒计时重置回 7 天。
     本脚本每天跑一次，把所有 Bot/Site 全部续期，永不停止。

登录态：__Host-mrtcloud_token（JWT，约 26 天有效，过期需重新登录抓取）

通知：复用 notify.py（Telegram + SMTP 双通道，失败不阻断续期）。
依赖：requests（pip install requests）
"""

import os
import sys
import json
from datetime import datetime

import requests

from notify import send_notification

API = "https://cloud.puratya.com/api"

# Cloudflare 对 Python 默认 UA 返回 403 (error 1010)，需伪装成浏览器
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def http(path, method="GET", token=None):
    """请求 API，返回 (status_code, body)。网络异常返回 (0, 错误信息)。"""
    headers = {"User-Agent": UA}
    if token:
        headers["Cookie"] = "__Host-mrtcloud_token=" + token
    if method != "GET":
        headers["Content-Type"] = "application/json"
    try:
        resp = requests.request(method, API + path, headers=headers, timeout=30)
        return resp.status_code, resp.text
    except requests.RequestException as e:
        return 0, str(e)


def now_str():
    """本地时间（workflow 里设 TZ=Asia/Shanghai 则显示北京时间）。"""
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")


def collect(token):
    """拉取所有 Bot / Site，返回 [(kind, id, name, remaining_hours), ...]。"""
    items = []
    for kind, path, key in [("Bot", "/bots", "bots"), ("Site", "/sites", "sites")]:
        status, body = http(path, token=token)
        if status != 200:
            print("[!] 获取 {} 失败: HTTP {} {}".format(path, status, body))
            items.append((kind, None, "<列表获取失败 HTTP {}>".format(status), None))
            continue
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = []
        lst = data if isinstance(data, list) else data.get(key, [])
        for obj in lst or []:
            oid = obj.get("id")
            name = obj.get("name") or obj.get("username") or "id:{}".format(oid)
            timer = obj.get("timer") or {}
            rem = timer.get("remaining_hours")
            items.append((kind, oid, name, rem))
    return items


def renew_one(token, kind, oid):
    """续期单个对象，返回 (ok, status, body)。"""
    path = "/bots/{}/renew".format(oid) if kind == "Bot" else "/sites/{}/renew".format(oid)
    status, body = http(path, method="POST", token=token)
    return (status == 200), status, body


def main():
    token = os.environ.get("MWS_TOKEN", "").strip()
    if not token:
        print("[✗] 环境变量 MWS_TOKEN 未设置")
        sys.exit(1)

    # 0) 验证 token 有效性
    status, body = http("/auth/me", token=token)
    if status == 401:
        title = "⚠️ MWS token 已失效 ({})".format(now_str())
        content = ("请重新登录 cloud.puratya.com，F12 抓取 __Host-mrtcloud_token，"
                   "更新到 GitHub Secret MWS_TOKEN")
        print(title)
        print(content)
        send_notification(content, title=title)
        sys.exit(1)
    if status != 200:
        print("[✗] 验证 token 异常: HTTP {} {}".format(status, body))
        sys.exit(1)

    try:
        who = json.loads(body).get("username")
    except (json.JSONDecodeError, AttributeError):
        who = "?"
    print("[✓] 登录有效: {}".format(who))

    # 1) 拉取并续期
    items = collect(token)
    if not items:
        title = "MWS 续期报告 ({}) · 无对象".format(now_str())
        print(title)
        send_notification("账号下没有 Bot / Site，跳过。", title=title)
        return

    lines = []
    failed = 0
    for kind, oid, name, rem in items:
        if oid is None:
            lines.append("  · {} {}：列表获取失败".format(kind, name))
            failed += 1
            continue
        ok, status, body = renew_one(token, kind, oid)
        rem_txt = "，续期前剩 {}h".format(int(rem)) if rem is not None else ""
        if ok:
            lines.append("  · {} {}：续期成功{}".format(kind, name, rem_txt))
            print("[✓] {} {} (id:{}) 续期成功{}".format(kind, name, oid, rem_txt))
        else:
            lines.append("  · {} {}：续期失败 HTTP {} {}".format(kind, name, status, body.strip()))
            failed += 1
            print("[✗] {} {} (id:{}) 续期失败 HTTP {}".format(kind, name, oid, status))

    # 2) 汇总 + 通知
    status_word = "完成" if failed == 0 else "部分失败"
    title = "MWS 续期报告 ({}) · {}".format(now_str(), status_word)
    content = "\n".join(lines)
    print("\n" + title + "\n" + content)
    send_notification(content, title=title)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
