import asyncio
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright
import httpx

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

async def izvuci_stream(url: str):
    m3u8_url = None
    referer = url

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
            print(f"✅ Pronađen stream")
            # Vraćamo proxy URL umjesto direktnog CDN linka
            import urllib.parse
            encoded = urllib.parse.quote(m3u8_url, safe='')
            proxy_url = f"https://parabellum-backend-uykk.onrender.com/proxy?url={encoded}"
            return {"success": True, "url": proxy_url}
        else:
            return {"success": False, "error": "Stream nije pronađen"}

    except Exception as e:
        print(f"❌ Greška: {str(e)}")
        return {"success": False, "error": str(e)}

@app.get("/proxy")
async def proxy_stream(url: str):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.gledajbesplatno.com/",
            "Origin": "https://www.gledajbesplatno.com",
        }
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=headers, timeout=30)
            
            content_type = res.headers.get("content-type", "application/vnd.apple.mpegurl")
            
            # Ako je m3u8 fajl, trebamo proxovati i sve segmente unutar njega
            if "mpegurl" in content_type or url.endswith(".m3u8"):
                content = res.text
                # Replacujemo relativne URL-ove sa proxy URL-ovima
                lines = content.split('\n')
                new_lines = []
                base_url = url.rsplit('/', 1)[0] + '/'
                
                for line in lines:
                    if line.startswith('http'):
                        import urllib.parse
                        encoded = urllib.parse.quote(line.strip(), safe='')
                        new_lines.append(f"https://parabellum-backend-uykk.onrender.com/proxy?url={encoded}")
                    elif line.endswith('.m3u8') or line.endswith('.ts') or line.endswith('.aac'):
                        full_url = base_url + line.strip()
                        import urllib.parse
                        encoded = urllib.parse.quote(full_url, safe='')
                        new_lines.append(f"https://parabellum-backend-uykk.onrender.com/proxy?url={encoded}")
                    else:
                        new_lines.append(line)
                
                return Response(
                    content='\n'.join(new_lines),
                    media_type="application/vnd.apple.mpegurl",
                    headers={
                        "Access-Control-Allow-Origin": "*",
                        "Cache-Control": "no-cache",
                    }
                )
            else:
                return Response(
                    content=res.content,
                    media_type=content_type,
                    headers={
                        "Access-Control-Allow-Origin": "*",
                    }
                )
    except Exception as e:
        print(f"Proxy greška: {str(e)}")
        return Response(content=str(e), status_code=500)

@app.get("/health")
def health():
    return {"status": "ok"}