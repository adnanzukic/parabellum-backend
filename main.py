import asyncio
import urllib.parse
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

# 🔥 GLOBALNI COOKIES
session_cookies = {}


async def izvuci_stream(url: str):
    global session_cookies

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
            ],
        )

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            viewport={"width": 1280, "height": 720},
        )

        page = await context.new_page()

        # 🔥 NAJBITNIJI FIX — RESPONSE LISTENER
        def handle_response(response):
            nonlocal m3u8_url
            url_res = response.url

            if ".m3u8" in url_res:
                print("🎥 M3U8 FOUND:", url_res)
                m3u8_url = url_res

        page.on("response", handle_response)

        print("🌐 Otvaram:", url)

        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # 🔥 čekaj da se sve učita
        await page.wait_for_load_state("networkidle")

        # 🔥 dodatno čekanje (player loading)
        await asyncio.sleep(10)

        # 🔥 pokušaj klik na play
        try:
            await page.click(".jw-icon-display", timeout=5000)
        except:
            pass

        # 🔥 čekanje da se pojavi m3u8
        for _ in range(30):
            if m3u8_url:
                break
            await asyncio.sleep(1)

        # 🔥 COOKIES
        cookies = await context.cookies()
        session_cookies = {cookie["name"]: cookie["value"] for cookie in cookies}

        print("🍪 Cookies:", session_cookies)

        await browser.close()

    return m3u8_url


@app.get("/stream")
async def get_stream(
    slug: str,
    type: str = "movie",
    sezona: int = 1,
    epizoda: int = 1,
):
    try:
        if type == "movie":
            url = f"https://www.gledajbesplatno.com/film/{slug}/watching.html"
        else:
            url = f"https://www.gledajbesplatno.com/serija/{slug}/sezona/{sezona}/epizoda/{epizoda}"

        print(f"🔄 Tražimo: {url}")

        m3u8_url = await izvuci_stream(url)

        if m3u8_url:
            encoded = urllib.parse.quote(m3u8_url, safe="")
            proxy_url = f"https://parabellum-backend-uykk.onrender.com/proxy?url={encoded}"

            print("✅ PROXY:", proxy_url)

            return {"success": True, "url": proxy_url}
        else:
            print("❌ NIJE PRONAĐEN STREAM")
            return {"success": False, "error": "Stream nije pronađen"}

    except Exception as e:
        print(f"❌ Greška: {str(e)}")
        return {"success": False, "error": str(e)}


@app.get("/proxy")
async def proxy_stream(url: str):
    try:
        global session_cookies

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://gledajbesplatno.com/",
            "Origin": "https://gledajbesplatno.com",
        }

        async with httpx.AsyncClient(cookies=session_cookies) as client:
            res = await client.get(url, headers=headers, timeout=30)

            content_type = res.headers.get(
                "content-type", "application/vnd.apple.mpegurl"
            )

            # 🔥 M3U8 rewrite
            if "mpegurl" in content_type or ".m3u8" in url:
                content = res.text
                lines = content.split("\n")

                new_lines = []
                base_url = url.rsplit("/", 1)[0] + "/"

                for line in lines:
                    line = line.strip()

                    if line.startswith("http"):
                        encoded = urllib.parse.quote(line, safe="")
                        new_lines.append(
                            f"https://parabellum-backend-uykk.onrender.com/proxy?url={encoded}"
                        )

                    elif any(x in line for x in [".m3u8", ".ts", ".aac"]):
                        full_url = base_url + line
                        encoded = urllib.parse.quote(full_url, safe="")
                        new_lines.append(
                            f"https://parabellum-backend-uykk.onrender.com/proxy?url={encoded}"
                        )

                    else:
                        new_lines.append(line)

                return Response(
                    content="\n".join(new_lines),
                    media_type="application/vnd.apple.mpegurl",
                    headers={"Access-Control-Allow-Origin": "*"},
                )

            return Response(
                content=res.content,
                media_type=content_type,
                headers={"Access-Control-Allow-Origin": "*"},
            )

    except Exception as e:
        print("❌ Proxy greška:", str(e))
        return Response(content=str(e), status_code=500)


@app.get("/health")
def health():
    return {"status": "ok"}