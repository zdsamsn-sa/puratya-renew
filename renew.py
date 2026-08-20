#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MWS (cloud.puratya.com) 自动续期脚本 (Playwright UI点击 + API强制续期 + TG截图版)
"""

import os
import sys
import json
import requests
from datetime import datetime

from playwright.sync_api import sync_playwright
from notify import send_notification

BASE_URL = "https://cloud.puratya.com"
API_BASE = f"{BASE_URL}/api"
SCREENSHOT_DIR = "./screenshots"

def now_str():
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def send_tg_photo(photo_path, caption=""):
    """通过 Telegram Bot API 发送图片。"""
    tg_token = os.environ.get("TG_BOT_TOKEN", "").strip()
    tg_chat_id = os.environ.get("TG_CHAT_ID", "").strip()
    
    if not tg_token or not tg_chat_id:
        print("[-] 未配置 TG_BOT_TOKEN 或 TG_CHAT_ID，跳过发送截图。")
        return False
        
    url = f"https://api.telegram.org/bot{tg_token}/sendPhoto"
    try:
        with open(photo_path, 'rb') as f:
            resp = requests.post(
                url,
                data={"chat_id": tg_chat_id, "caption": caption, "parse_mode": "HTML"},
                files={"photo": f},
                timeout=30
            )
        if resp.status_code == 200:
            print(f"  [TG] 截图推送成功: {os.path.basename(photo_path)}")
            return True
        else:
            print(f"  [TG] 截图推送失败: HTTP {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        print(f"  [TG] 截图推送异常: {e}")
        return False

def collect_via_api(api_context):
    """通过 Playwright 共享的上下文调用 API 拉取列表。"""
    items = {}
    for kind, path, key in [("Bot", "/bots", "bots"), ("Site", "/sites", "sites")]:
        resp = api_context.get(API_BASE + path)
        if not resp.ok:
            continue
        try:
            data = resp.json()
        except Exception:
            data = []
            
        lst = data if isinstance(data, list) else data.get(key, [])
        for obj in lst or []:
            oid = str(obj.get("id"))
            name = obj.get("name") or obj.get("username") or f"id:{oid}"
            timer = obj.get("timer") or {}
            rem = timer.get("remaining_hours")
            
            unique_key = f"{kind}-{oid}"
            items[unique_key] = {
                "kind": kind,
                "id": oid,
                "name": name,
                "rem": rem
            }
    return items

def main():
    token = os.environ.get("MWS_TOKEN", "").strip()
    if not token:
        print("[✗] 环境变量 MWS_TOKEN 未设置")
        sys.exit(1)

    ensure_dir(SCREENSHOT_DIR)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # 1. 注入 Token
        context.add_cookies([{
            "name": "__Host-mrtcloud_token",
            "value": token,
            "domain": "cloud.puratya.com",
            "path": "/",
            "secure": True
        }])

        page = context.new_page()

        # 2. 验证登录有效性
        resp = context.request.get(f"{API_BASE}/auth/me")
        if resp.status == 401:
            title = f"⚠️ MWS token 已失效 ({now_str()})"
            content = "请重新登录抓取 __Host-mrtcloud_token，更新 MWS_TOKEN"
            print(f"{title}\n{content}")
            send_notification(content, title=title)
            sys.exit(1)

        try:
            who = resp.json().get("username", "?")
        except:
            who = "?"
        print(f"[✓] 登录有效，当前用户: {who}")

        # 3. 拉取续期前的数据
        items_before = collect_via_api(context.request)
        if not items_before:
            print("账号下没有 Bot / Site，跳过。")
            browser.close()
            return
            
        print(f"[*] 发现 {len(items_before)} 个对象，准备执行续期操作...")

        # 4. 访问主面板并截图 (修复 404，直接访问根目录)
        print(f"\n[*] 正在加载主控制面板: {BASE_URL}")
        page.goto(BASE_URL)
        page.wait_for_timeout(5000) # 等待页面完全加载
        
        # 5. 尝试 UI 点击续期
        renew_buttons = page.locator("button:has-text('Renew'), button:has-text('续期'), a:has-text('Renew'), a:has-text('续期')")
        count = renew_buttons.count()
        if count == 0:
            print(f"  [!] 面板中未发现明显的 Renew 按钮 (将使用后台 API 强制续期)")
        else:
            for i in range(count):
                try:
                    renew_buttons.nth(i).click()
                    print(f"  👆 成功点击第 {i+1}/{count} 个 UI 续期按钮")
                    page.wait_for_timeout(1500)
                except Exception as e:
                    pass

        # 6. 【核心保障】调用浏览器内置请求，强制发起续期 POST (无视UI是否存在)
        print("\n[*] 正在触发 API 强制续期，确保万无一失...")
        for key, data in items_before.items():
            kind, oid, name = data["kind"], data["id"], data["name"]
            api_path = f"/bots/{oid}/renew" if kind == "Bot" else f"/sites/{oid}/renew"
            try:
                # 借用 Playwright context 的 HTTP 客户端，自带登录态且不触发 CF 拦截
                post_resp = context.request.post(API_BASE + api_path)
                if post_resp.ok:
                    print(f"  -> [API] 成功发送 {kind} [{name}] 续期指令")
                else:
                    print(f"  -> [API] {kind} [{name}] 续期指令返回 HTTP {post_resp.status}")
            except Exception as e:
                print(f"  -> [API] {kind} [{name}] 续期请求异常: {e}")
        
        # 等待后端数据落盘并刷新页面截图
        page.wait_for_timeout(3000)
        page.reload()
        page.wait_for_timeout(5000)
        after_pic = f"{SCREENSHOT_DIR}/panel_after.png"
        page.screenshot(path=after_pic, full_page=True)
        print(f"  📸 已保存最终面板截图: {after_pic}")

        # 7. 验证最终续期结果
        print("\n[*] 正在验证最终续期结果...")
        items_after = collect_via_api(context.request)
        
        lines = []
        failed = 0
        
        for key, before_data in items_before.items():
            kind, name = before_data["kind"], before_data["name"]
            rem_before = before_data["rem"]
            rem_after = items_after.get(key, {}).get("rem")
            
            if rem_after is not None and (rem_after > (rem_before or 0) or rem_after >= 167):
                status_txt = f"✅ 续期成功 (前: {int(rem_before or 0)}h -> 后: {int(rem_after)}h)"
                lines.append(f"  · {kind} {name}：{status_txt}")
                print(f"[✓] {kind} {name}: {status_txt}")
            else:
                status_txt = f"❌ 续期失败或无变化 (前: {int(rem_before or 0)}h -> 后: {int(rem_after or 0)}h)"
                lines.append(f"  · {kind} {name}：{status_txt}")
                print(f"[✗] {kind} {name}: {status_txt}")
                failed += 1
                
        status_word = "完成" if failed == 0 else "部分失败"
        title = f"MWS 续期报告 ({now_str()}) · {status_word}"
        content = "\n".join(lines)
        
        # 发送文本通知
        send_notification(content, title=title)
        
        # 发送 Telegram 截图
        print("\n[*] 开始推送截图到 Telegram...")
        caption = f"<b>{title}</b>\n\n此为 <b>控制面板主页</b> 续期执行后的最新状态截图。\n\n{content}"
        send_tg_photo(after_pic, caption)
        
        browser.close()
        
        if failed > 0:
            sys.exit(1)

if __name__ == "__main__":
    main()
