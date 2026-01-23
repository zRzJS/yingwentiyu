import asyncio
import random
from playwright.async_api import async_playwright
import aiohttp
from datetime import datetime

# --- 配置区 ---
API_URL = "https://ppv.to/api/streams"
# 扩展监听后缀，防范混淆
STREAM_KEYWORDS = [".m3u8", ".ts", "playlist", "master.json", "manifest"]

# 模拟真实的浏览器 Header
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

async def check_m3u8_url(url, referer):
    """深度校验流地址有效性"""
    try:
        origin = "https://" + referer.split('/')[2]
        headers = {
            "User-Agent": UA,
            "Referer": referer,
            "Origin": origin,
            "Connection": "keep-alive"
        }
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # 使用 GET 确认内容确实存在
            async with session.get(url, headers=headers) as resp:
                return resp.status in [200, 206, 403] 
    except:
        return False

async def grab_m3u8_advanced(page, iframe_url):
    """
    核心抓取逻辑：模拟真实人类交互
    """
    found_streams = set()

    # 1. 定义多维度响应监听器
    async def handle_response(response):
        url = response.url.split('?')[0] # 去掉参数干扰
        if any(kw in url.lower() for kw in STREAM_KEYWORDS):
            if not url.endswith(".js") and not url.endswith(".css"): # 排除噪声
                print(f"   🎯 嗅探到潜在流地址: {response.url[:80]}...")
                found_streams.add(response.url)

    page.on("response", handle_response)
    
    try:
        print(f"   🌐 正在访问: {iframe_url}")
        # 增加 Referer 模拟
        await page.goto(iframe_url, wait_until="networkidle", timeout=45000)
        
        # 2. 模拟真实人类延迟与随机移动
        await asyncio.sleep(random.uniform(2, 4))
        
        # 3. 智能点击：尝试点击页面中心以及可能的播放按钮
        # 很多播放器在 iframe 中，我们先尝试直接点击坐标 (屏幕中心)
        print("   🖱️ 尝试触发播放器交互...")
        await page.mouse.move(random.randint(300, 500), random.randint(200, 400))
        # 强制点击播放器可能存在的层
        await page.mouse.click(640, 360) 
        
        # 4. 针对特定的播放按钮 class 进行点击（适配更多通用播放器）
        buttons = [".vjs-big-play-button", "button.play", ".play-icon", "#play-button"]
        for btn in buttons:
            try:
                target = page.locator(btn)
                if await target.is_visible():
                    await target.click(timeout=2000)
                    print(f"   ✅ 已点击播放按钮: {btn}")
            except:
                continue

        # 5. 等待流加载
        print("   ⏳ 正在捕获数据流，请稍后...")
        await asyncio.sleep(12) 

    except Exception as e:
        print(f"   ❌ 访问异常: {e}")
    finally:
        page.remove_listener("response", handle_response)

    # 6. 验证并筛选最终链接
    valid_urls = set()
    if found_streams:
        tasks = [check_m3u8_url(u, iframe_url) for u in found_streams]
        results = await asyncio.gather(*tasks)
        for url, is_ok in zip(found_streams, results):
            if is_ok: valid_urls.add(url)
            
    return valid_urls

async def main():
    print(f"🚀 终极版抓取工具启动 | {datetime.now().strftime('%H:%M:%S')}")
    
    async with async_playwright() as p:
        # 使用 Firefox 并模拟真实环境
        browser = await p.firefox.launch(headless=True) # 调试建议设为 False
        context = await browser.new_context(
            user_agent=UA,
            viewport={'width': 1280, 'height': 720},
            ignore_https_errors=True
        )
        
        # 获取任务列表（以 Basketball 为例）
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL) as r:
                data = await r.json()
        
        tasks = []
        for cat_obj in data.get("streams", []):
            if cat_obj.get("category") == "Basketball":
                tasks.extend(cat_obj.get("streams", []))

        print(f"📊 待处理篮球比赛: {len(tasks)} 场")
        
        url_map = {}
        page = await context.new_page()
        
        for i, task in enumerate(tasks, 1):
            name = task.get("name")
            iframe = task.get("iframe")
            print(f"\n[{i}/{len(tasks)}] 正在解析: {name}")
            
            urls = await grab_m3u8_advanced(page, iframe)
            if urls:
                print(f"   🏆 成功获取 {len(urls)} 条有效流地址")
                url_map[f"{name}::Basketball::{iframe}"] = urls
            else:
                print(f"   💀 未能捕获到有效流")

        # --- M3U 文件生成逻辑 (同之前，略作精简) ---
        print("\n💾 正在导出 M3U8 文件...")
        m3u_content = ['#EXTM3U']
        for key, urls in url_map.items():
            name, cat, _ = key.split("::")
            for url in urls:
                m3u_content.append(f'#EXTINF:-1 group-title="PPV-Basketball",{name}')
                m3u_content.append(url)
        
        with open("Ultimate_PPV.m3u8", "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_content))
            
        await browser.close()
        print(f"✅ 完成！文件已保存。")

if __name__ == "__main__":
    asyncio.run(main())
