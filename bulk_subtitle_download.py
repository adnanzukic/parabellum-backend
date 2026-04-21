import time
from dataclasses import dataclass
from typing import Dict, List

import requests

TMDB_API_KEY = "0027b6950390b7bf784ae1836716816d"
BACKEND_URL = "https://parabellum-backend-uykk.onrender.com"
REQUEST_DELAY_SECONDS = 3
MAX_DOWNLOADS_PER_RUN = 30
TV_MAX_SEASONS = 3
TV_MAX_EPISODES = 10
TMDB_MIN_VOTE_COUNT = 100
TMDB_GENRE_WESTERN = 37


@dataclass
class MediaItem:
    tmdb_id: int
    title: str
    media_type: str  # "movie" or "tv"
    vote_average: float
    vote_count: int


def fetch_tmdb_discover(media_type: str, page: int = 1) -> Dict:
    base = "https://api.themoviedb.org/3/discover/movie" if media_type == "movie" else "https://api.themoviedb.org/3/discover/tv"
    params = {
        "with_genres": TMDB_GENRE_WESTERN,
        "sort_by": "vote_average.desc",
        "vote_count.gte": TMDB_MIN_VOTE_COUNT,
        "api_key": TMDB_API_KEY,
        "page": page,
    }
    response = requests.get(base, params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def collect_western_titles(max_items_per_type: int = 20) -> List[MediaItem]:
    items: List[MediaItem] = []
    for media_type in ["movie", "tv"]:
        page = 1
        collected = 0
        while collected < max_items_per_type:
            payload = fetch_tmdb_discover(media_type=media_type, page=page)
            results = payload.get("results", [])
            if not results:
                break

            for raw in results:
                title = raw.get("title") if media_type == "movie" else raw.get("name")
                if not title:
                    continue
                items.append(
                    MediaItem(
                        tmdb_id=raw["id"],
                        title=title,
                        media_type=media_type,
                        vote_average=float(raw.get("vote_average") or 0),
                        vote_count=int(raw.get("vote_count") or 0),
                    )
                )
                collected += 1
                if collected >= max_items_per_type:
                    break
            page += 1
    return items


def call_subtitles_fallback(params: Dict, context_label: str) -> bool:
    endpoint = f"{BACKEND_URL}/subtitles-fallback"
    print(f"[REQ] {context_label} -> {endpoint} params={params}")
    try:
        response = requests.get(endpoint, params=params, timeout=45)
        data = response.json() if response.headers.get("content-type", "").startswith("application/json") else None
        subtitles_count = len(data) if isinstance(data, list) else 0
        print(
            f"[RES] {context_label} status={response.status_code} subtitles={subtitles_count} "
            "source=unknown (endpoint trenutno ne vraća cache/new indikator)"
        )
        return response.status_code == 200
    except Exception as exc:
        print(f"[ERR] {context_label} error={exc}")
        return False


def run_bulk_cache_warmup() -> None:
    if TMDB_API_KEY == "YOUR_TMDB_API_KEY":
        raise ValueError("Postavi TMDB_API_KEY konstantu prije pokretanja skripte.")

    print("[START] Dohvat western filmova i serija sa TMDB (vote_count.gte=100).")
    titles = collect_western_titles(max_items_per_type=20)
    print(f"[INFO] Ukupno dohvaćenih naslova: {len(titles)}")

    total_requests = 0
    successful_requests = 0

    for item in titles:
        if total_requests >= MAX_DOWNLOADS_PER_RUN:
            print(f"[STOP] Dostignut limit od {MAX_DOWNLOADS_PER_RUN} requesta.")
            break

        print(
            f"[TITLE] Obrada: {item.title} ({item.media_type}) "
            f"tmdb_id={item.tmdb_id} rating={item.vote_average} votes={item.vote_count}"
        )

        if item.media_type == "movie":
            params = {"tmdb_id": item.tmdb_id, "type": "movie"}
            ok = call_subtitles_fallback(params, context_label=f"MOVIE {item.title}")
            total_requests += 1
            successful_requests += 1 if ok else 0
            if total_requests < MAX_DOWNLOADS_PER_RUN:
                time.sleep(REQUEST_DELAY_SECONDS)
            continue

        for season in range(1, TV_MAX_SEASONS + 1):
            for episode in range(1, TV_MAX_EPISODES + 1):
                if total_requests >= MAX_DOWNLOADS_PER_RUN:
                    break
                params = {
                    "tmdb_id": item.tmdb_id,
                    "type": "tv",
                    "season": season,
                    "episode": episode,
                }
                label = f"TV {item.title} S{season:02d}E{episode:02d}"
                ok = call_subtitles_fallback(params, context_label=label)
                total_requests += 1
                successful_requests += 1 if ok else 0
                if total_requests < MAX_DOWNLOADS_PER_RUN:
                    time.sleep(REQUEST_DELAY_SECONDS)
            if total_requests >= MAX_DOWNLOADS_PER_RUN:
                break

    print(
        f"[DONE] Završeno. Ukupno requesta: {total_requests}, "
        f"uspješnih: {successful_requests}, neuspješnih: {total_requests - successful_requests}"
    )


if __name__ == "__main__":
    run_bulk_cache_warmup()
