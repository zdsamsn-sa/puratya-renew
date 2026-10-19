#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MWS (cloud.m-ws.cc) 自动续期脚本
原理：MWS 的 Bot/Site 有 7 天倒计时，到期自动停止。
     点一次 Renew 按钮 = POST /api/bots/{id}/renew，把倒计时重置回 7 天。
     本脚本每周一、三、五跑一次，把所有 Bot/Site 全部续期，永不停止。
登录态：__Host-mrtcloud_token（JWT，约 26 天有效）。
     每次成功请求若服务端通过 Set-Cookie 下发新 token，脚本会自动捕获，
     并在续期成功后用 GitHub CLI 把新 token 写回仓库 Secret MWS_TOKEN，
     从而保证 token 永不过期（需额外配置 GH_PAT）。
通知：走 notify-gateway（notify.py 上报结构化结果，网关统一发邮件 + Telegram）。
     仓库只需配 NOTIFY_URL / NOTIFY_TOKEN，不内置 SMTP / TG。
依赖：requests（pip install requests）；更新 Secret 需要 gh CLI（GitHub Actions 自带）
"""
import os
import sys
import json
import subprocess
import urllib.error
from datetime import datetime
import requests
from notify import notify

API = "https://cloud.m-ws.cc/api"
# Cloudflare 对 Python 默认 UA 返回 403 (error 1010)，需伪装成浏览器
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
COOKIE_NAME = "__Host-mrtcloud_token"


def http(path, method="GET", token=None):
    """请求 API，返回 (status_code, body, new_token)。

    new_token：若响应 Set-Cookie 中带有刷新后的 __Host-mrtcloud_token 则返回该值，
    否则返回 None。网络异常返回 (0, 错误信息, None)。
    """
    headers = {"User-Agent": UA}
    if token:
        headers["Cookie"] = COOKIE_NAME + "=" + token
    if method != "GET":
        headers["Content-Type"] = "application/json"
    try:
        resp = requests.request(method, API + path, headers=headers, timeout=30)
        new_token = None
        # requests 会自动解析 Set-Cookie 到 resp.cookies
        if COOKIE_NAME in resp.cookies:
            new_token = resp.cookies.get(COOKIE_NAME)
        # 部分环境下 cookies 字典可能拿不到，兜底解析 header
        if not new_token:
            set_cookie = resp.headers.get("Set-Cookie") or ""
            # 可能有多条，简单扫描
            for part in set_cookie.split(","):
                if COOKIE_NAME + "=" in part:
                    # 取第一个分号前的值
                    val = part.split(COOKIE_NAME + "=", 1)[1].split(";")[0].strip()
                    if val:
                        new_token = val
                        break
        return resp.status_code, resp.text, new_token
    except requests.RequestException as e:
        return 0, str(e), None


def now_str():
    """本地时间（workflow 里设 TZ=Asia/Shanghai 则显示北京时间）。"""
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")


def collect(token):
    """拉取所有 Bot / Site，返回 [(kind, id, name, remaining_hours), ...] 以及最新 token。"""
    items = []
    current = token
    for kind, path, key in [("Bot", "/bots", "bots"), ("Site", "/sites", "sites")]:
        status, body, new_token = http(path, token=current)
        if new_token:
            current = new_token
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
    return items, current


def renew_one(token, kind, oid):
    """续期单个对象，返回 (ok, status, body, new_token)。"""
    path = "/bots/{}/renew".format(oid) if kind == "Bot" else "/sites/{}/renew".format(oid)
    status, body, new_token = http(path, method="POST", token=token)
    return (status == 200), status, body, new_token


def update_github_secret(new_token):
    """把新 token 写回 GitHub Secret MWS_TOKEN。

    需要环境变量 GH_PAT（具有 repo 或 Secrets: Write 权限的 Personal Access Token）。
    GitHub Actions 的 GITHUB_TOKEN 无法更新 repository secrets，因此必须使用 PAT。
    返回 (success: bool, message: str)
    """
    pat = (os.environ.get("GH_PAT") or "").strip()
    if not pat:
        return False, "未配置 GH_PAT，跳过自动更新 Secret（请添加具有 secrets 写权限的 PAT）"

    env = os.environ.copy()
    env["GH_TOKEN"] = pat
    # 在 Actions 中运行时默认就是当前仓库，无需额外 --repo
    try:
        result = subprocess.run(
            ["gh", "secret", "set", "MWS_TOKEN", "--body", new_token],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return True, "已通过 gh secret set 更新 MWS_TOKEN"
        err = (result.stderr or result.stdout or "").strip()
        return False, "gh secret set 失败 (exit {}): {}".format(result.returncode, err)
    except FileNotFoundError:
        return False, "未找到 gh 命令（GitHub Actions 环境应自带）"
    except subprocess.TimeoutExpired:
        return False, "gh secret set 超时"
    except Exception as e:
        return False, "更新 Secret 异常: {}".format(e)


def _report(level, title, content, details):
    """上报 notify-gateway；失败只打日志，不阻断续期主流程。"""
    try:
        notify(title, content, level=level, details=details)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        print("::warning::通知上报失败 HTTP {}: {}".format(e.code, body))
    except Exception as e:
        print("::warning::通知上报失败: {}".format(e))


def main():
    original_token = os.environ.get("MWS_TOKEN", "").strip()
    if not original_token:
        print("[✗] 环境变量 MWS_TOKEN 未设置")
        sys.exit(1)

    current_token = original_token

    # 0) 验证 token 有效性
    status, body, new_token = http("/auth/me", token=current_token)
    if new_token:
        current_token = new_token
        print("[i] /auth/me 返回了新 token，已捕获")

    if status == 401:
        title = "⚠️ MWS token 已失效 ({})".format(now_str())
        content = ("请重新登录 cloud.m-ws.cc，F12 抓取 __Host-mrtcloud_token，"
                   "更新到 GitHub Secret MWS_TOKEN")
        print(title)
        print(content)
        _report("failed", title, content, None)
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
    items, current_token = collect(current_token)
    if not items:
        title = "MWS 续期报告 ({}) · 无对象".format(now_str())
        print(title)
        _report("success", title, "账号下没有 Bot / Site，跳过。", None)
        # 即使无对象，如果 token 已刷新也尝试更新
        if current_token != original_token:
            ok, msg = update_github_secret(current_token)
            print("[i] Token 已刷新，更新 Secret: {}".format(msg))
        return

    lines = []
    failed = 0
    detail_items = []
    for kind, oid, name, rem in items:
        if oid is None:
            lines.append("  · {} {}：列表获取失败".format(kind, name))
            detail_items.append({"id": "unknown", "name": name, "status": "failed",
                                 "error": "列表获取失败"})
            failed += 1
            continue
        ok, status, body, new_token = renew_one(current_token, kind, oid)
        if new_token:
            current_token = new_token
            print("[i] 续期 {} 时捕获到新 token".format(name))
        rem_txt = "，续期前剩 {}h".format(int(rem)) if rem is not None else ""
        if ok:
            lines.append("  · {} {}：续期成功{}".format(kind, name, rem_txt))
            msg = rem_txt.strip().lstrip("，") if rem is not None else ""
            detail_items.append({"id": str(oid), "name": name, "status": "success",
                                 "message": msg})
            print("[✓] {} {} (id:{}) 续期成功{}".format(kind, name, oid, rem_txt))
        else:
            lines.append("  · {} {}：续期失败 HTTP {} {}".format(kind, name, status, body.strip()))
            detail_items.append({"id": str(oid), "name": name, "status": "failed",
                                 "error": "HTTP {} {}".format(status, body.strip())})
            failed += 1
            print("[✗] {} {} (id:{}) 续期失败 HTTP {}".format(kind, name, oid, status))

    # 2) 汇总 + 通知
    total = len(items)
    success = total - failed
    level = "success" if failed == 0 else "partial"
    status_word = "完成" if failed == 0 else "部分失败"
    title = "MWS 续期报告 ({}) · {}".format(now_str(), status_word)
    content = "\n".join(lines)
    print("\n" + title + "\n" + content)

    # 3) 若捕获到新 token，自动写回 GitHub Secret（优先在全部成功时更新）
    token_updated = False
    token_update_msg = ""
    if current_token != original_token:
        ok, msg = update_github_secret(current_token)
        token_updated = ok
        token_update_msg = msg
        if ok:
            print("[✓] {}".format(msg))
            content += "\n\n[自动更新] MWS_TOKEN 已刷新并写回 GitHub Secret"
        else:
            print("[!] {}".format(msg))
            content += "\n\n[自动更新] 捕获到新 token，但写回 Secret 失败: {}".format(msg)
    else:
        print("[i] 本次未收到新 token（服务端可能未刷新 cookie），MWS_TOKEN 保持不变")

    _report(
        level,
        title,
        content,
        {
            "total": total,
            "success": success,
            "failed": failed,
            "details": detail_items,
            "token_refreshed": current_token != original_token,
            "token_secret_updated": token_updated,
            "token_update_message": token_update_msg,
        },
    )
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
