import asyncio
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

async def izvuci_stream(url: str) -> str | None:
    m3u8_url = None
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process",
                "--no-zygote",
                "--disable-blink-features=AutomationControlled",
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
        )
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

@app.get("/stream")
async def get_stream(slug: str, type: str = "movie", sezona: int = 1, epizoda: int = 1, source: str = "gledajbesplatno"):
    try:
        if source == "filmoviplex":
            if type == "movie":
                url = f"https://www.filmoviplex.com/film/{slug}/watching.html"
            else:
                url = f"https://www.filmoviplex.com/serija/{slug}/sezona/{sezona}/epizoda/{epizoda}"
        else:
            if type == "movie":
                url = f"https://www.gledajbesplatno.com/film/{slug}/watching.html"
            else:
                url = f"https://www.gledajbesplatno.com/serija/{slug}/sezona/{sezona}/epizoda/{epizoda}"

        print(f"🔄 Tražimo stream: {url}")
        m3u8_url = await izvuci_stream(url)

        if m3u8_url:
            print(f"✅ Pronađen: {m3u8_url[:50]}...")
            return {"success": True, "url": m3u8_url}
        else:
            print("❌ Stream nije pronađen")
            return {"success": False, "error": "Stream nije pronađen"}

    except Exception as e:
        print(f"❌ Greška: {str(e)}")
        return {"success": False, "error": str(e)}

@app.get("/health")
def health():
    return {"status": "ok"}