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

            # 🔥 hvata sve m3u8 requestove (iz svih frame-ova)
            def handle_response(response):
                nonlocal m3u8_url
                if ".m3u8" in response.url and "master" in response.url:
                    print(f"[FOUND] {response.url}")
                    m3u8_url = response.url

            page.on("response", handle_response)

            page.goto(url, timeout=60000)

            print("[INFO] Tražim iframe...")

            iframe = None

            try:
                page.wait_for_selector("iframe", timeout=10000)
                frames = page.query_selector_all("iframe")

                print(f"[INFO] Nađeno iframe-ova: {len(frames)}")

                # uzmi prvi koji ima content
                for i, frame_element in enumerate(frames):
                    try:
                        frame = frame_element.content_frame()
                        if frame:
                            iframe = frame
                            print(f"[INFO] Koristim iframe #{i}")
                            break
                    except:
                        continue

            except:
                print("[WARN] Nema iframe")

            # fallback ako nema iframe
            if not iframe:
                iframe = page

            print("[INFO] Pokušavam klik...")

            try:
                iframe.mouse.click(500, 400)
                print("[INFO] Klik izvršen")
            except:
                print("[WARN] Klik nije uspio")

            print("[INFO] Čekam stream (20s)...")
            page.wait_for_timeout(20000)

            browser.close()

            if m3u8_url:
                return {"success": True, "stream": m3u8_url}
            else:
                return {"success": False, "error": "Nije pronađen m3u8"}

    except Exception as e:
        print("[ERROR]")
        traceback.print_exc()
        return {"success": False, "error": str(e)}