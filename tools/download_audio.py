"""Download the credited recordings and create mobile-compatible MP3 assets."""
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
HEADERS = {"User-Agent": "SoundViewer/1.0 (educational sound and image viewer)"}
RECORDINGS = [
    ("dog", "강아지", "Dog", "동물", "멍멍! 반가워요.", "https://freesound.org/people/vdr3/sounds/393694/"),
    ("cat", "고양이", "Cat", "동물", "야옹, 내 목소리를 들어 봐요.", "https://freesound.org/people/tuberatanka/sounds/110011/"),
    ("cow", "소", "Cow", "동물", "음메~ 농장의 친구예요.", "https://freesound.org/people/JarredGibb/sounds/233129/"),
    ("car", "자동차", "Car", "탈것", "부릉부릉, 출발해요.", "https://freesound.org/people/jackthemurray/sounds/433584/"),
    ("fire-engine", "소방차", "Fire engine", "탈것", "불을 끄러 출동해요.", "https://freesound.org/people/Breviceps/sounds/465700/"),
    ("airplane", "비행기", "Airplane", "탈것", "슈우웅! 하늘을 날아요.", "https://freesound.org/people/InspectorJ/sounds/428086/"),
    ("train", "기차", "Train", "탈것", "기차의 힘찬 경적을 들어 봐요.", "https://freesound.org/people/sgo.75/sounds/845065/"),
    ("ambulance", "구급차", "Ambulance", "탈것", "도움이 필요한 곳으로 출동해요.", "https://freesound.org/people/LanDub/sounds/184623/"),
]


def get(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=90) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == 2:
                raise
            delay = int(error.headers.get("Retry-After", "120"))
            print(f"Source rate limited; respecting Retry-After: {delay}s", flush=True)
            for chunk in range(0, delay, 30):
                time.sleep(min(30, delay - chunk))


def main():
    source_dir = ROOT / ".cache/source-audio"
    audio_dir = ROOT / "assets/audio"
    source_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)
    catalog = []
    for ident, name, english, category, caption, page_url in RECORDINGS:
        page = get(page_url).decode("utf-8")
        title_match = re.search(r'<h1[^>]*>\s*(?:<a[^>]*>)?(.*?)</(?:a|h1)>', page, re.S)
        license_match = re.search(r'<a[^>]+title="Go to the full license text"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page, re.S)
        preview_match = re.search(r'https://cdn\.freesound\.org/previews/[^"\s]+-hq\.mp3', page)
        if not title_match or not license_match or not preview_match:
            raise ValueError(f"Review source page: {page_url}")
        title = html.unescape(re.sub("<[^>]+>", "", title_match[1])).strip()
        license_url = license_match[1].replace("http://", "https://")
        allowed = {"https://creativecommons.org/publicdomain/zero/1.0/": "CC0 1.0",
                   "https://creativecommons.org/licenses/by/4.0/": "CC BY 4.0"}
        if license_url not in allowed:
            raise ValueError(f"Review license before download: {page_url}: {license_url}")
        license_name = allowed[license_url]
        preview_url = preview_match[0]
        source = source_dir / (ident + ".mp3")
        if not source.exists():
            source.write_bytes(get(preview_url))
        output = audio_dir / (ident + ".mp3")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
                        "-t", "15", "-vn", "-af", "loudnorm=I=-20:TP=-3:LRA=7", "-ar", "44100",
                        "-ac", "1", "-c:a", "libmp3lame", "-b:a", "96k", str(output)], check=True)
        author = urllib.parse.unquote(urllib.parse.urlparse(page_url).path.split("/")[2])
        duration = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                         "format=duration", "-of", "default=nw=1:nk=1", str(output)]))
        catalog.append({"id": ident, "name": name, "english": english, "category": category,
                        "caption": caption, "image": f"assets/images/{ident}.png", "audio": f"assets/audio/{ident}.mp3",
                        "duration": round(duration, 1), "credit": {"title": title, "author": author,
                        "source": page_url, "download": preview_url,
                        "license": license_name, "licenseUrl": license_url,
                        "changes": "Downloaded the public high-quality MP3 preview; converted to mono MP3, volume normalized and limited to the first 15 seconds.",
                        "originalSha256": hashlib.sha256(source.read_bytes()).hexdigest()}})
        print(f"Ready: {ident} ({duration:.1f}s, {output.stat().st_size:,} bytes), {license_name}", flush=True)
    (ROOT / "catalog.js").write_text("globalThis.SOUND_CATALOG = " + json.dumps(catalog, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")


if __name__ == "__main__":
    main()
