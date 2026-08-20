#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MWS (cloud.puratya.com) 自动续期脚本 (Playwright 浏览器自动化版)

原理：
  1. 注入 JWT token，免密登录。
  2. 使用 Playwright 真实打开浏览器页面，截取续期前状态。
  3. 模拟人类操作，遍历点击所有的“Renew”按钮。
  4. 截取续期后状态，保存到本地。
  5. 调用内部 API 再次拉取数据，双重验证剩余时间是否已重置回 7 天，确保续期成功。

依赖：pip install playwright requests && playwright install chromium
通知：复用 notify.py（需支持接收纯文本）
"""

import os
import sys
import time
import json
from datetime import datetime

# 导入 Playwright
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from notify import send_notification

BASE_URL = "https://cloud.puratya.com"
API_BASE = f"{BASE_URL}/api"
SCREENSHOT_DIR = "./screenshots"

def now_str():
    """本地时间（workflow 里设 TZ=Asia/Shanghai 则显示北京时间）。"""
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def collect_via_api(api_context):
    """
    通过 Playwright 共享的上下文调用 API 拉取所有 Bot / Site
    返回字典格式，方便后续比对: { "Bot-123": {"name": "xxx", "rem": 168}, ... }
    """
    items = {}
    for kind, path, key in [("Bot", "/bots", "bots"), ("Site", "/sites", "sites")]:
        resp = api_context.get(API_BASE + path)
        if not resp.ok:
            print(f"[!] 获取 {path} 失败: HTTP {resp.status} {resp.status_text}")
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
        # 启动 Chromium (在服务器上运行请保持 headless=True，本地调试可设为 False)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # 1. 注入 Token，建立登录态
        context.add_cookies([{
            "name": "__Host-mrtcloud_token",
            "value": token,
            "domain": "cloud.puratya.com",
            "path": "/",
            "secure": True
        }])

        page = context.new_page()

        # 2. 验证 Token 有效性 (通过请求个人信息接口)
        resp = context.request.get(f"{API_BASE}/auth/me")
        if resp.status == 401:
            title = f"⚠️ MWS token 已失效 ({now_str()})"
            content = "请重新登录 cloud.puratya.com，F12 抓取 __Host-mrtcloud_token，更新到 GitHub Secret MWS_TOKEN"
            print(f"{title}\n{content}")
            send_notification(content, title=title)
            sys.exit(1)
        elif not resp.ok:
            print(f"[✗] 验证 token 异常: HTTP {resp.status} {resp.status_text}")
            sys.exit(1)

        try:
            who = resp.json().get("username", "?")
        except Exception:
            who = "?"
        print(f"[✓] 登录有效，当前用户: {who}")

        # 3. 记录续期前的数据
        items_before = collect_via_api(context.request)
        if not items_before:
            title = f"MWS 续期报告 ({now_str()}) · 无对象"
            print(title)
            send_notification("账号下没有 Bot / Site，跳过。", title=title)
            browser.close()
            return
            
        print(f"[*] 发现 {len(items_before)} 个对象，准备执行页面点击续期...")

        # 4. 分别进入 Bot 和 Site 页面执行真实点击与截图
        # (如果 Bot 和 Site 在同一个面板页面，只需访问主页即可。这里假设分别有两个路由)
        target_pages = [("Bot", f"{BASE_URL}/bots"), ("Site", f"{BASE_URL}/sites")]
        
        for kind, url in target_pages:
            print(f"[*] 正在处理 {kind} 页面: {url}")
            page.goto(url)
            page.wait_for_load_state("networkidle")
            time.sleep(2) # 缓冲等待页面数据渲染
            
            # 截图：续期前
            before_pic = f"{SCREENSHOT_DIR}/{kind}_before_{datetime.now().strftime('%Y%m%d%H%M')}.png"
            page.screenshot(path=before_pic, full_page=True)
            print(f"  📸 已保存续期前截图: {before_pic}")
            
            # 定位所有的 Renew 按钮并点击
            # 注意：如果按钮文本不是 "Renew" (例如是图标或中文 "续期")，请修改下方的定位器
            renew_buttons = page.locator("button:has-text('Renew')")
            count = renew_buttons.count()
            
            if count == 0:
                print(f"  [!] 页面中未发现 Renew 按钮 (可能无需续期或已满)")
            else:
                for i in range(count):
                    try:
                        renew_buttons.nth(i).click()
                        print(f"  👆 点击了第 {i+1}/{count} 个 Renew 按钮")
                        time.sleep(1.5) # 点击后等待请求发送及UI更新
                    except Exception as e:
                        print(f"  [✗] 点击按钮时发生异常: {e}")
            
            # 截图：续期后
            after_pic = f"{SCREENSHOT_DIR}/{kind}_after_{datetime.now().strftime('%Y%m%d%H%M')}.png"
            page.screenshot(path=after_pic, full_page=True)
            print(f"  📸 已保存续期后截图: {after_pic}")

        # 5. 双重验证：再次调用 API，确保剩余时间已重置 (满时间为 7天 = 168 小时)
        print("\n[*] 正在通过 API 验证续期结果...")
        time.sleep(3) # 等待后端数据彻底落盘
        items_after = collect_via_api(context.request)
        
        lines = []
        failed = 0
        
        for key, before_data in items_before.items():
            kind, name = before_data["kind"], before_data["name"]
            rem_before = before_data["rem"]
            
            after_data = items_after.get(key, {})
            rem_after = after_data.get("rem")
            
            # 如果续期后的时间大于续期前，或者已经非常接近 168 小时，则视为成功
            if rem_after is not None and (rem_after > (rem_before or 0) or rem_after >= 167):
                status_txt = f"续期成功 (前: {int(rem_before or 0)}h -> 后: {int(rem_after)}h)"
                lines.append(f"  · {kind} {name}：{status_txt}")
                print(f"[✓] {kind} {name}: {status_txt}")
            else:
                status_txt = f"续期失败/无变化 (前: {int(rem_before or 0)}h -> 后: {int(rem_after or 0)}h)"
                lines.append(f"  · {kind} {name}：{status_txt}")
                print(f"[✗] {kind} {name}: {status_txt}")
                failed += 1
                
        # 6. 汇总通知
        status_word = "完成" if failed == 0 else "部分失败"
        title = f"MWS 续期报告 ({now_str()}) · {status_word}"
        content = "\n".join(lines)
        print(f"\n{title}\n{content}")
        
        # 备注：截图已保存在本地 ./screenshots 目录下。
        # 您的 notify.py 若支持发送附件，可自行将 before_pic 和 after_pic 传入 send_notification
        send_notification(content, title=title)
        
        browser.close()
        
        if failed > 0:
            sys.exit(1)

if __name__ == "__main__":
    main()
