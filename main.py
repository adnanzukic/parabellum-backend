import asyncio
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENSUBTITLES_API_KEY = "RqSzAupFUlPoiIaLh6dXwxdmpX2kUaPN"
OPENSUBTITLES_BASE = "https://api.opensubtitles.com/api/v1"

@app.get("/subtitles")
async def get_subtitles(tmdb_id: int, type: str = "movie", sezona: int = 1, epizoda: int = 1):
    try:
        headers = {
            "Api-Key": OPENSUBTITLES_API_KEY,
            "Content-Type": "application/json",
            "User-Agent": "Parabellum v1.0"
        }

        for jezik in ["sr", "hr", "bs"]:
            params = {
                "tmdb_id": tmdb_id,
                "languages": jezik,
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
                
                print(f"Status: {res.status_code}")
                print(f"Response: {res.text[:500]}")
                
                if res.status_code != 200:
                    return {"success": False, "error": f"API status {res.status_code}: {res.text[:200]}"}

                data = res.json()

                if data.get("data") and len(data["data"]) > 0:
                    subtitle = data["data"][0]
                    file_id = subtitle["attributes"]["files"][0]["file_id"]

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
                            "jezik": jezik
                        }

        return {"success": False, "error": "Titlovi nisu pronađeni"}

    except Exception as e:
        print(f"Greška: {str(e)}")
        return {"success": False, "error": str(e)}

        # Tražimo titlove — prvo srpski, pa hrvatski
        for jezik in ["sr", "hr", "bs"]:
            params = {
                "tmdb_id": tmdb_id,
                "languages": jezik,
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
                timeout=15,
                follow_redirects=True
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
                            "jezik": jezik
                        }

        return {"success": False, "error": "Titlovi nisu pronađeni"}

    except Exception as e:
        print(f"Greška: {str(e)}")
        return {"success": False, "error": str(e)}

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
            )
    except Exception as e:
        return Response(content=str(e), status_code=500)

@app.get("/health")
def health():
    return {"status": "ok"}