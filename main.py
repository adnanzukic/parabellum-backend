import asyncio
import os
from typing import Optional

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
import httpx
from supabase import create_client

app = FastAPI()

# CORS (da app može pristupiti backendu)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY")
OPENSUBTITLES_API_KEY = os.environ.get("OPENSUBTITLES_API_KEY")
OPENSUBTITLES_BASE = "https://api.opensubtitles.com/api/v1"
SUPABASE_BUCKET = "subtitles"
SELF_HEALTH_URL = "https://parabellum-backend-uykk.onrender.com/health"
SELF_PING_INTERVAL_SECONDS = 14 * 60


def get_label(path: str) -> str:
    if "_sr" in path:
        return "Srpski 2" if "_2" in path else "Srpski"
    if "_hr" in path:
        return "Hrvatski 2" if "_2" in path else "Hrvatski"
    return "Prijevod"


def make_storage_path(
    tmdb_id: int,
    media_type: str,
    season: int,
    episode: int,
    lang: str,
    idx: int,
) -> str:
    suffix = "" if idx == 1 else f"_{idx}"
    if media_type == "movie":
        return f"{tmdb_id}_movie_{lang}{suffix}.srt"
    return f"{tmdb_id}_tv_{season}_{episode}_{lang}{suffix}.srt"


def get_cache_candidates(tmdb_id: int, media_type: str, season: int, episode: int) -> list[str]:
    if media_type == "movie":
        return [
            f"{tmdb_id}_movie_sr.srt",
            f"{tmdb_id}_movie_sr_2.srt",
            f"{tmdb_id}_movie_hr.srt",
            f"{tmdb_id}_movie_hr_2.srt",
        ]
    return [
        f"{tmdb_id}_tv_{season}_{episode}_sr.srt",
        f"{tmdb_id}_tv_{season}_{episode}_sr_2.srt",
        f"{tmdb_id}_tv_{season}_{episode}_hr.srt",
        f"{tmdb_id}_tv_{season}_{episode}_hr_2.srt",
    ]

@app.get("/")
def root():
    return {"status": "radi"}


async def self_ping_loop():
    while True:
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
                res = await client.get(SELF_HEALTH_URL)
                print(f"[SELF-PING] /health status_code={res.status_code}")
        except Exception as e:
            print(f"[SELF-PING] error={str(e)}")
        await asyncio.sleep(SELF_PING_INTERVAL_SECONDS)


@app.on_event("startup")
async def startup_event():
    print("[SELF-PING] Starting background self-ping task")
    asyncio.create_task(self_ping_loop())


@app.get("/subtitles")
async def get_subtitles(
    tmdb_id: int,
    type: str = "movie",
    sezona: int = 1,
    epizoda: int = 1,
    jezik: Optional[str] = None,
):
    try:
        headers = {
            "Api-Key": OPENSUBTITLES_API_KEY,
            "Content-Type": "application/json",
            "User-Agent": "Parabellum v1.0"
        }

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

            async with httpx.AsyncClient(follow_redirects=True) as client:
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
                        json={"file_id": file_id}
                    )
                    download_data = download_res.json()
                    download_link = download_data.get("link")

                    if download_link:
                        return {
                            "success": True,
                            "url": download_link,
                            "jezik": lang
                        }

        return {"success": False, "error": "Titlovi nisu pronađeni"}

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return {"success": False, "error": str(e)}

@app.get("/subtitle-file")
async def get_subtitle_file(url: str):
    """Proxy za SRT fajl da zaobiđemo CORS"""
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            res = await client.get(url, timeout=15)
            return Response(
                content=res.content,
                media_type="text/plain",
                headers={"Access-Control-Allow-Origin": "*"}
            )
    except Exception as e:
        return Response(content=str(e), status_code=500)


@app.get("/subtitles-fallback")
async def get_subtitles_fallback(
    tmdb_id: int,
    type: str = "movie",
    season: int = 1,
    episode: int = 1,
):
    print(
        f"[FALLBACK] Request received tmdb_id={tmdb_id} type={type} "
        f"season={season} episode={episode}"
    )
    if type not in {"movie", "tv"}:
        print(f"[FALLBACK] Invalid type={type}. Returning []")
        return []
    if not SUPABASE_URL:
        print("[FALLBACK] SUPABASE_URL missing. Returning []")
        return []

    cache_paths = get_cache_candidates(tmdb_id, type, season, episode)
    cached_results: list[dict] = []
    print(f"[FALLBACK] Cache paths to check: {cache_paths}")

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            for path in cache_paths:
                url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{path}"
                print(f"[FALLBACK] Cache check HEAD {url}")
                try:
                    r = await client.head(url, timeout=8)
                    if r.status_code == 200:
                        print(f"[FALLBACK] Cache HIT path={path}")
                        cached_results.append({"file": url, "label": get_label(path)})
                    else:
                        print(
                            f"[FALLBACK] Cache MISS path={path} status_code={r.status_code}"
                        )
                except Exception:
                    print(f"[FALLBACK] Cache check error path={path}")
                    continue
    except Exception:
        print("[FALLBACK] Cache phase failed due to client-level exception")
        pass

    if cached_results:
        print(
            f"[FALLBACK] Returning {len(cached_results)} cached subtitle(s) "
            f"without OpenSubtitles call"
        )
        return cached_results

    if not OPENSUBTITLES_API_KEY or not SUPABASE_KEY:
        print(
            "[FALLBACK] Missing OPENSUBTITLES_API_KEY or SUPABASE_SECRET_KEY. "
            "Returning []"
        )
        return []

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    uploaded_results: list[dict] = []

    headers = {
        "Api-Key": OPENSUBTITLES_API_KEY,
        "Content-Type": "application/json",
        "User-Agent": "Parabellum v1.0",
    }

    os_type = "movie" if type == "movie" else "episode"
    print(f"[FALLBACK] OpenSubtitles search type={os_type}")

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            for lang in ["sr", "hr"]:
                params = {
                    "tmdb_id": tmdb_id,
                    "languages": lang,
                    "type": os_type,
                }
                if os_type == "episode":
                    params["season_number"] = season
                    params["episode_number"] = episode

                print(f"[FALLBACK] OpenSubtitles search lang={lang} params={params}")
                res = await client.get(
                    f"{OPENSUBTITLES_BASE}/subtitles",
                    headers=headers,
                    params=params,
                    timeout=15,
                )
                print(
                    f"[FALLBACK] OpenSubtitles response lang={lang} "
                    f"status_code={res.status_code}"
                )
                if res.status_code == 429:
                    print(
                        f"[FALLBACK] Rate limited on search lang={lang}. "
                        f"Returning cached_results={len(cached_results)}"
                    )
                    return cached_results
                if res.status_code != 200:
                    print(f"[FALLBACK] Skipping lang={lang} due to non-200 search status")
                    continue

                payload = res.json()
                data = payload.get("data") or []
                print(f"[FALLBACK] OpenSubtitles results count lang={lang}: {len(data)}")
                if not data:
                    continue

                ranked = sorted(
                    data,
                    key=lambda item: item.get("attributes", {}).get("download_count") or 0,
                    reverse=True,
                )[:2]
                print(
                    f"[FALLBACK] Ranked top results lang={lang}: {len(ranked)} candidate(s)"
                )

                for idx, subtitle in enumerate(ranked, start=1):
                    files = subtitle.get("attributes", {}).get("files") or []
                    if not files:
                        print(
                            f"[FALLBACK] Skipping ranked idx={idx} lang={lang}: "
                            "no files in attributes"
                        )
                        continue
                    file_id = files[0].get("file_id")
                    if not file_id:
                        print(
                            f"[FALLBACK] Skipping ranked idx={idx} lang={lang}: "
                            "missing file_id"
                        )
                        continue
                    download_count = (
                        subtitle.get("attributes", {}).get("download_count") or 0
                    )
                    print(
                        f"[FALLBACK] Candidate lang={lang} idx={idx} "
                        f"file_id={file_id} download_count={download_count}"
                    )

                    download_res = await client.post(
                        f"{OPENSUBTITLES_BASE}/download",
                        headers=headers,
                        json={"file_id": file_id},
                        timeout=15,
                    )
                    print(
                        f"[FALLBACK] Download link request lang={lang} idx={idx} "
                        f"file_id={file_id} status_code={download_res.status_code}"
                    )
                    if download_res.status_code == 429:
                        print(
                            f"[FALLBACK] Rate limited on download lang={lang} idx={idx}. "
                            f"Returning cached_results={len(cached_results)}"
                        )
                        return cached_results
                    if download_res.status_code != 200:
                        print(
                            f"[FALLBACK] Skipping lang={lang} idx={idx} due to "
                            "non-200 download response"
                        )
                        continue

                    download_data = download_res.json()
                    download_link = download_data.get("link")
                    if not download_link:
                        print(
                            f"[FALLBACK] Missing download link lang={lang} idx={idx}"
                        )
                        continue

                    srt_res = await client.get(
                        download_link,
                        headers=headers,
                        timeout=20,
                    )
                    print(
                        f"[FALLBACK] SRT fetch lang={lang} idx={idx} "
                        f"status_code={srt_res.status_code}"
                    )
                    if srt_res.status_code != 200:
                        print(
                            f"[FALLBACK] Skipping upload lang={lang} idx={idx} due to "
                            "failed SRT fetch"
                        )
                        continue

                    storage_path = make_storage_path(tmdb_id, type, season, episode, lang, idx)
                    try:
                        supabase.storage.from_(SUPABASE_BUCKET).upload(
                            path=storage_path,
                            file=srt_res.content,
                            file_options={"content-type": "text/plain", "upsert": "true"},
                        )
                        print(
                            f"[FALLBACK] Supabase upload success lang={lang} idx={idx} "
                            f"path={storage_path}"
                        )
                    except Exception:
                        print(
                            f"[FALLBACK] Supabase upload error lang={lang} idx={idx} "
                            f"path={storage_path}"
                        )
                        continue

                    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{storage_path}"
                    uploaded_results.append({"file": public_url, "label": get_label(storage_path)})
                    print(
                        f"[FALLBACK] Added public subtitle lang={lang} idx={idx} "
                        f"label={get_label(storage_path)}"
                    )
    except Exception as e:
        print(f"[FALLBACK] Unexpected error in OpenSubtitles/upload phase: {str(e)}")
        return cached_results

    print(f"[FALLBACK] Returning uploaded_results count={len(uploaded_results)}")
    return uploaded_results


@app.get("/health")
def health():
    return {"status": "ok"}
