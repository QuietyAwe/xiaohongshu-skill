#!/usr/bin/env python3
"""
小红书扫码登录脚本
自动获取 Cookie 并保存到 .env 文件

使用方法:
    python xhs_login.py

依赖安装:
    pip install playwright python-dotenv
    playwright install chromium
"""

import os
import sys
import asyncio
import re
from pathlib import Path
from datetime import datetime

try:
    from playwright.async_api import async_playwright
    from dotenv import load_dotenv, set_key
except ImportError as e:
    print(f"缺少依赖: {e}")
    print("请运行: pip install playwright python-dotenv")
    print("然后运行: playwright install chromium")
    sys.exit(1)


# 小红书登录页面
LOGIN_URL = "https://www.xiaohongshu.com"
# 二维码截图保存路径
QR_CODE_PATH = Path(__file__).parent.parent / "assets" / "qrcode.png"


def get_env_path() -> Path:
    """获取 .env 文件路径"""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.parent.exists():
        env_path.parent.mkdir(parents=True, exist_ok=True)
    return env_path


def save_cookie_to_env(cookie_string: str, env_path: Path):
    """保存 Cookie 到 .env 文件"""
    if not env_path.exists():
        env_path.write_text("# 小红书 Cookie 配置\n\n")
    
    set_key(env_path, "XHS_COOKIE", cookie_string)
    print(f"\n✅ Cookie 已保存到: {env_path}")


def format_cookie(cookies: list) -> str:
    """将 Cookie 列表格式化为字符串"""
    return "; ".join([f"{c['name']}={c['value']}" for c in cookies])


async def wait_for_login(page) -> bool:
    """等待登录成功"""
    print("\n⏳ 等待扫码登录...")
    print(f"   📱 请用小红书 APP 扫描二维码")
    print(f"   📁 二维码图片: {QR_CODE_PATH}")
    
    max_wait = 180  # 最长等待 3 分钟
    start_time = asyncio.get_event_loop().time()
    
    while True:
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed > max_wait:
            print("\n⏰ 登录超时，请重新运行脚本")
            return False
        
        # 检查 Cookie 中是否有登录标识
        try:
            cookies = await page.context.cookies()
            cookie_dict = {c['name']: c['value'] for c in cookies}
            
            # 检查是否有登录后的关键 Cookie
            if cookie_dict.get('a1') and cookie_dict.get('web_session'):
                # 再检查一下是否真的登录了（有用户信息）
                try:
                    # 尝试获取用户信息 API
                    await page.wait_for_timeout(2000)  # 等待登录完成
                    
                    # 检查页面是否有登录后的元素
                    user_info = await page.query_selector('[class*="user"], [class*="avatar"], .user-info')
                    if user_info:
                        return True
                    
                    # 或者检查 URL 是否变化
                    current_url = page.url
                    if 'login' not in current_url.lower():
                        return True
                        
                except:
                    pass
        except:
            pass
        
        # 显示等待提示
        remaining = int(max_wait - elapsed)
        if int(elapsed) % 10 == 0 and int(elapsed) > 0:
            print(f"   ⏳ 还剩 {remaining} 秒...")
        
        await asyncio.sleep(1)


async def login_and_get_cookie() -> str:
    """打开浏览器，等待扫码登录，返回 Cookie"""
    # 确保目录存在
    QR_CODE_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    async with async_playwright() as p:
        # 启动浏览器（headless 模式，WSL 无图形界面）
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        page = await context.new_page()
        
        print("🌐 正在打开小红书...")
        await page.goto(LOGIN_URL, wait_until='networkidle')
        
        # 等待页面加载
        await page.wait_for_timeout(2000)
        
        # 尝试点击登录按钮
        try:
            # 查找登录按钮
            login_btns = await page.query_selector_all('button, [class*="login"]')
            for btn in login_btns:
                text = await btn.text_content()
                if text and '登录' in text:
                    await btn.click()
                    await page.wait_for_timeout(1500)
                    break
        except Exception as e:
            print(f"   提示: {e}")
        
        # 查找二维码
        print("🔍 正在定位二维码...")
        await page.wait_for_timeout(2000)
        
        # 尝试多种方式找到二维码
        qr_element = None
        selectors = [
            'canvas',
            'img[src*="qr"]',
            'img[src*="QR"]',
            '[class*="qr"]',
            '[class*="QR"]',
            'img[alt*="二维码"]',
            'img[alt*="扫码"]',
        ]
        
        for selector in selectors:
            try:
                elements = await page.query_selector_all(selector)
                for elem in elements:
                    # 检查元素大小，二维码通常是正方形且有一定大小
                    box = await elem.bounding_box()
                    if box and box['width'] > 100 and box['height'] > 100:
                        qr_element = elem
                        print(f"   ✓ 找到二维码元素: {selector}")
                        break
                if qr_element:
                    break
            except:
                continue
        
        # 如果找到二维码元素，截图
        if qr_element:
            await qr_element.screenshot(path=str(QR_CODE_PATH))
            print(f"\n📸 二维码已保存到: {QR_CODE_PATH}")
            print("   请打开此图片，用小红书 APP 扫码登录")
        else:
            # 截取整个页面
            print("   未找到二维码元素，尝试截取整个页面...")
            await page.screenshot(path=str(QR_CODE_PATH), full_page=False)
            print(f"\n📸 页面截图已保存到: {QR_CODE_PATH}")
            print("   请查看截图中的二维码，用小红书 APP 扫码登录")
        
        # 等待登录成功
        success = await wait_for_login(page)
        
        if not success:
            await browser.close()
            return None
        
        print("\n✅ 登录成功！正在获取 Cookie...")
        
        # 等待一下确保 Cookie 完整
        await page.wait_for_timeout(2000)
        
        # 获取所有 Cookie
        cookies = await context.cookies()
        cookie_string = format_cookie(cookies)
        
        # 提取关键信息
        cookie_dict = {c['name']: c['value'] for c in cookies}
        
        print(f"\n📋 Cookie 信息:")
        print(f"   a1: {cookie_dict.get('a1', '未找到')[:20]}...")
        print(f"   web_session: {cookie_dict.get('web_session', '未找到')[:20]}...")
        
        await browser.close()
        
        return cookie_string


async def main_async():
    """主函数"""
    print("=" * 50)
    print("🦞 小红书扫码登录")
    print("=" * 50)
    
    # 执行登录
    cookie = await login_and_get_cookie()
    
    if not cookie:
        print("\n❌ 登录失败")
        return 1
    
    # 保存到 .env
    env_path = get_env_path()
    save_cookie_to_env(cookie, env_path)
    
    print("\n🎉 完成！现在可以使用发布脚本了")
    print(f"   运行: python publish_xhs.py -t '标题' -d '内容' -i image.png")
    
    return 0


def main():
    exit_code = asyncio.run(main_async())
    sys.exit(exit_code)


if __name__ == '__main__':
    main()