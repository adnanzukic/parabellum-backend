<<<<<<< HEAD
from typing import Optional

=======
>>>>>>> be33dbd07237cab6f113d7d2ee5e408ed174e34c
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI()

# CORS (da app može pristupiti backendu)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENSUBTITLES_API_KEY = "RqSzAupFUlPoiIaLh6dXwxdmpX2kUaPN"
OPENSUBTITLES_BASE = "https://api.opensubtitles.com/api/v1"

<<<<<<< HEAD
=======

@app.get("/")
def root():
    return {"status": "radi"}


# 🔥 GLAVNA FUNKCIJA ZA TITLOVE
>>>>>>> be33dbd07237cab6f113d7d2ee5e408ed174e34c
@app.get("/subtitles")
async def get_subtitles(
    tmdb_id: int,
    type: str = "movie",
    sezona: int = 1,
<<<<<<< HEAD
    epizoda: int = 1,
    jezik: Optional[str] = None,
=======
    epizoda: int = 1
>>>>>>> be33dbd07237cab6f113d7d2ee5e408ed174e34c
):
    try:
        headers = {
            "Api-Key": OPENSUBTITLES_API_KEY,
            "Content-Type": "application/json",
            "User-Agent": "Parabellum v1.0"
        }

<<<<<<< HEAD
        jezici_za_pretragu = [jezik] if (jezik and jezik.strip()) else ["sr", "hr", "bs"]

        for lang in jezici_za_pretragu:
            params = {
                "tmdb_id": tmdb_id,
                "languages": lang,
                "type": type,
            }
            if type == "episode":
                params["season_number"] = sezona
                params["episode_number"] = epizoda

            async with httpx.AsyncClient() as client:
                res = await client.get(
                    f"{OPENSUBTITLES_BASE}/subtitles",
                    headers=headers,
                    params=params,
                    timeout=15
                )
                data = res.json()

                if data.get("data") and len(data["data"]) > 0:
                    # Uzmi prvi rezultat
                    subtitle = data["data"][0]
                    file_id = subtitle["attributes"]["files"][0]["file_id"]

                    # Dohvati download link
                    download_res = await client.post(
                        f"{OPENSUBTITLES_BASE}/download",
                        headers=headers,
                        json={"file_id": file_id, "sub_format": "srt"}
                    )
                    download_data = download_res.json()
                    download_link = download_data.get("link")

                    if download_link:
                        return {
                            "success": True,
                            "url": download_link,
                            "jezik": lang
                        }

=======
        async with httpx.AsyncClient(follow_redirects=True) as client:

            # probaj redom jezike
            for jezik in ["sr", "hr", "bs"]:
                params = {
                    "tmdb_id": tmdb_id,
                    "languages": jezik,
                    "type": type,
                }

                if type == "episode":
                    params["season_number"] = sezona
                    params["episode_number"] = epizoda

                print(f"[INFO] Tražim titl: {jezik}")

                res = await client.get(
                    f"{OPENSUBTITLES_BASE}/subtitles",
                    headers=headers,
                    params=params,
                    timeout=15
                )

                print(f"[INFO] Status: {res.status_code}")

                if res.status_code != 200:
                    print(f"[WARN] API error: {res.text[:200]}")
                    continue  # pokušaj sljedeći jezik

                data = res.json()

                if data.get("data"):
                    subtitle = data["data"][0]
                    file_id = subtitle["attributes"]["files"][0]["file_id"]

                    print(f"[INFO] Nađen file_id: {file_id}")

                    download_res = await client.post(
                        f"{OPENSUBTITLES_BASE}/download",
                        headers=headers,
                        json={
                            "file_id": file_id,
                            "sub_format": "srt"
                        }
                    )

                    download_data = download_res.json()
                    download_link = download_data.get("link")

                    if download_link:
                        print(f"[SUCCESS] Titl pronađen ({jezik})")

                        return {
                            "success": True,
                            "url": download_link,
                            "jezik": jezik
                        }

        print("[INFO] Nema titlova ni za jedan jezik")
>>>>>>> be33dbd07237cab6f113d7d2ee5e408ed174e34c
        return {"success": False, "error": "Titlovi nisu pronađeni"}

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return {"success": False, "error": str(e)}

<<<<<<< HEAD
@app.get("/subtitle-file")
async def get_subtitle_file(url: str):
    """Proxy za SRT fajl da zaobiđemo CORS"""
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(url, timeout=15)
            return Response(
                content=res.content,
                media_type="text/plain",
                headers={"Access-Control-Allow-Origin": "*"}
=======

# 🔥 PROXY ZA TITL (da WebView može učitati)
@app.get("/subtitle-file")
async def get_subtitle_file(url: str):
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            res = await client.get(url, timeout=15)

            return Response(
                content=res.content,
                media_type="text/plain",
                headers={
                    "Access-Control-Allow-Origin": "*"
                }
>>>>>>> be33dbd07237cab6f113d7d2ee5e408ed174e34c
            )
    except Exception as e:
        return Response(content=str(e), status_code=500)

<<<<<<< HEAD
=======

# HEALTH CHECK
>>>>>>> be33dbd07237cab6f113d7d2ee5e408ed174e34c
@app.get("/health")
def health():
    return {"status": "ok"}