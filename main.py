import asyncio
import sys
import json
import subprocess
import tempfile
import os

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SCRAPER_SCRIPT = """
import asyncio
import sys
import json

async def scrape(url):
    from playwright.async_api import async_playwright
    m3u8_url = None
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--window-size=1280,720",
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
            java_script_enabled=True,
        )

        # Uklanjamo webdriver flag koji Cloudflare detektuje
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        page = await context.new_page()

        def handle_request(request):
            nonlocal m3u8_url
            if "master.m3u8" in request.url:
                m3u8_url = request.url

        page.on("request", handle_request)
        
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(4)
        
        try:
            await page.click(".jw-icon-display", timeout=3000)
        except:
            pass

        for _ in range(25):
            if m3u8_url:
                break
            await asyncio.sleep(1)

        await browser.close()
    
    return m3u8_url

url = sys.argv[1]
result = asyncio.run(scrape(url))
print(json.dumps({"url": result}))
"""

@app.get("/stream")
def get_stream(slug: str, type: str = "movie", sezona: int = 1, epizoda: int = 1):
    try:
        if type == "movie":
            url = f"https://www.gledajbesplatno.com/film/{slug}/watching.html"
        else:
            url = f"https://www.gledajbesplatno.com/serija/{slug}/sezona/{sezona}/epizoda/{epizoda}"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(SCRAPER_SCRIPT)
            temp_path = f.name

        result = subprocess.run(
            [sys.executable, temp_path, url],
            capture_output=True,
            text=True,
            timeout=60
        )

        os.unlink(temp_path)

        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr[:200] if result.stderr else "")

        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip())
            if data.get("url"):
                return {"success": True, "url": data["url"]}

        return {"success": False, "error": "Stream nije pronađen"}

    except Exception as e:
        print(f"Greška: {str(e)}")
        return {"success": False, "error": str(e)}

@app.get("/health")
def health():
    return {"status": "ok"}