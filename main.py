from fastapi import FastAPI, Query
from playwright.sync_api import sync_playwright
import traceback

app = FastAPI()

@app.get("/")
def root():
    return {"status": "radi"}

@app.get("/get-stream")
def get_stream(url: str = Query(...)):
    try:
        print(f"[INFO] Otvaram URL: {url}")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            m3u8_url = None

            def handle_response(response):
                nonlocal m3u8_url
                if ".m3u8" in response.url and "master" in response.url:
                    print(f"[FOUND] {response.url}")
                    m3u8_url = response.url

            page.on("response", handle_response)

            page.goto(url, timeout=60000)

            print("[INFO] Čekam player...")
            page.wait_for_timeout(15000)

            browser.close()

            if m3u8_url:
                return {"success": True, "stream": m3u8_url}
            else:
                return {"success": False, "error": "Nije pronađen m3u8"}

    except Exception as e:
        print("[ERROR]")
        traceback.print_exc()
        return {"success": False, "error": str(e)}