"""Download the credited recordings and create mobile-compatible MP3 assets."""
import hashlib
import html
import json
import math
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
    ("horse", "말", "Horse", "동물", "히이잉! 힘차게 달리는 친구예요.", "https://freesound.org/people/Salsero_classic/sounds/826753/"),
    ("sheep", "양", "Sheep", "동물", "메에~ 포근한 털을 가진 친구예요.", "https://freesound.org/people/TheKingOfGeeks360/sounds/840891/"),
    ("pig", "돼지", "Pig", "동물", "꿀꿀, 농장에서 인사해요.", "https://freesound.org/people/qubodup/sounds/442907/"),
    ("duck", "오리", "Duck", "동물", "꽥꽥! 물가의 친구를 만나 봐요.", "https://freesound.org/people/gibarroule/sounds/365133/"),
    ("rooster", "수탉", "Rooster", "동물", "꼬끼오! 아침을 알려요.", "https://freesound.org/people/cabled_mess/sounds/391313/"),
    ("lion", "사자", "Lion", "동물", "어흥! 사자의 울음소리를 들어 봐요.", "https://freesound.org/people/Bidone/sounds/69572/"),
    ("elephant", "코끼리", "Elephant", "동물", "뿌우! 긴 코를 가진 커다란 친구예요.", "https://freesound.org/people/ikbenraar/sounds/819668/"),
    ("car", "자동차", "Car", "탈것", "부릉부릉, 출발해요.", "https://freesound.org/people/jackthemurray/sounds/433584/"),
    ("fire-engine", "소방차", "Fire engine", "탈것", "불을 끄러 출동해요.", "https://freesound.org/people/Breviceps/sounds/465700/"),
    ("airplane", "비행기", "Airplane", "탈것", "슈우웅! 하늘을 날아요.", "https://freesound.org/people/InspectorJ/sounds/428086/"),
    ("train", "기차", "Train", "탈것", "기차의 힘찬 경적을 들어 봐요.", "https://freesound.org/people/sgo.75/sounds/845065/"),
    ("ambulance", "구급차", "Ambulance", "탈것", "도움이 필요한 곳으로 출동해요.", "https://freesound.org/people/LanDub/sounds/184623/"),
    ("police-car", "경찰차", "Police car", "탈것", "사이렌을 울리며 출동해요.", "https://freesound.org/people/conleec/sounds/159753/"),
    ("motorcycle", "오토바이", "Motorcycle", "탈것", "부릉! 두 바퀴로 달려요.", "https://freesound.org/people/spenceomatic/sounds/119774/"),
    ("helicopter", "헬리콥터", "Helicopter", "탈것", "두두두두, 프로펠러를 돌리며 날아요.", "https://freesound.org/people/qubodup/sounds/187678/"),
    ("bus", "버스", "Bus", "탈것", "많은 사람을 태우고 달려요.", "https://freesound.org/people/bikesnbassboi/sounds/540398/"),
    ("ship", "배", "Ship", "탈것", "뿌우~ 바다 위에서 뱃고동이 울려요.", "https://freesound.org/people/coalcon/sounds/636075/"),
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


def audio_analysis(source, filters):
    result = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(source),
                             "-af", filters, "-f", "null", "-"],
                            check=True, capture_output=True, text=True, encoding="utf-8")
    return result.stderr


def loudness(source, prefix="anull"):
    log = audio_analysis(source, prefix + ",loudnorm=I=-20:TP=-4:LRA=50:print_format=json")
    match = re.search(r'\{\s*"input_i".*?\}', log, re.S)
    if not match:
        raise ValueError(f"No loudness measurement: {source}")
    return json.loads(match[0])


def exported_levels(source):
    # Audit the actual decoded MP3 with the EBU meter, independently of loudnorm's estimate.
    summary = audio_analysis(source, "ebur128=peak=true").rsplit("Summary:", 1)[-1]
    integrated = re.search(r"I:\s*([-\d.]+) LUFS", summary)
    peak = re.search(r"Peak:\s*([-\d.]+) dBFS", summary)
    if not integrated or not peak:
        raise ValueError(f"Invalid exported audio measurement: {source}")
    return float(integrated[1]), float(peak[1])


def normalize_audio(source, output):
    # Selecting one real channel avoids destructive cancellation in stereo field recordings.
    trim = "atrim=duration=15,asetpts=PTS-STARTPTS"
    log = audio_analysis(source, trim + ",astats=metadata=0:reset=0")
    levels = re.findall(r"Channel:\s*(\d+).*?RMS level dB:\s*([-\d.]+|[-+]?inf)", log, re.S)
    if not levels or not any(math.isfinite(float(level)) for _, level in levels):
        raise ValueError(f"Silent or invalid recording: {source}")
    channel = int(max(levels, key=lambda row: float(row[1]))[0]) - 1
    prefix = f"{trim},pan=mono|c0=c{channel},aresample=44100,apad=whole_dur=1"
    measured = loudness(source, prefix)
    if not math.isfinite(float(measured["input_i"])):
        raise ValueError(f"Recording too short or silent for loudness measurement: {source}")
    # Reduce excessive crest factor before matching loudness, rather than crushing isolated peaks.
    if float(measured["input_tp"]) - 20 - float(measured["input_i"]) > -4:
        peak_gain = -float(measured["input_tp"])
        prefix += f",volume={peak_gain}dB,acompressor=threshold=0.125893:ratio=4:attack=1:release=60"
        measured = loudness(source, prefix)
    normalizer = ("loudnorm=I=-20:TP=-4:LRA=50:linear=true"
                  f":measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
                  f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
                  f":offset={measured['target_offset']}")
    correction = 0
    for _ in range(5):
        # Re-render from the source, never re-encode a previous MP3; allow for encoder gain changes.
        filters = f"{prefix},{normalizer},volume={correction}dB,alimiter=limit=0.630957:level=false"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
                        "-vn", "-af", filters, "-ar", "44100", "-ac", "1",
                        "-c:a", "libmp3lame", "-b:a", "96k", str(output)], check=True)
        integrated, peak = exported_levels(output)
        if not math.isfinite(integrated):
            raise ValueError(f"Silent MP3 export: {output}")
        if abs(integrated + 20) <= 0.5 and peak <= -2.5:
            return {"integratedLufs": integrated, "truePeakDbtp": peak, "sourceChannel": channel + 1}
        correction += -20 - integrated
    raise ValueError(f"Export failed loudness check: {output}: {integrated} LUFS, {peak} dBTP")


def main():
    source_dir = ROOT / ".cache/source-audio"
    audio_dir = ROOT / "assets/audio"
    source_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)
    catalog = []
    catalog_path = ROOT / "catalog.js"
    previous = json.loads(catalog_path.read_text(encoding="utf-8").removeprefix("globalThis.SOUND_CATALOG = ").rstrip(";\n")) if catalog_path.exists() else []
    previous = {item["id"]: item["credit"] for item in previous}
    for ident, name, english, category, caption, page_url in RECORDINGS:
        old = previous.get(ident, {})
        if old.get("source") == page_url:
            title, license_url, preview_url = old["title"], old["licenseUrl"], old["download"]
        else:
            page = get(page_url).decode("utf-8")
            title_match = re.search(r'<h1[^>]*>\s*(?:<a[^>]*>)?(.*?)</(?:a|h1)>', page, re.S)
            license_match = re.search(r'<a[^>]+title="Go to the full license text"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page, re.S)
            preview_match = re.search(r'https://cdn\.freesound\.org/previews/[^"\s]+-hq\.mp3', page)
            if not title_match or not license_match or not preview_match:
                raise ValueError(f"Review source page: {page_url}")
            title = html.unescape(re.sub("<[^>]+>", "", title_match[1])).strip()
            license_url = license_match[1].replace("http://", "https://")
            preview_url = preview_match[0]
        allowed = {"https://creativecommons.org/publicdomain/zero/1.0/": "CC0 1.0",
                   "https://creativecommons.org/licenses/by/4.0/": "CC BY 4.0"}
        if license_url not in allowed:
            raise ValueError(f"Review license before download: {page_url}: {license_url}")
        license_name = allowed[license_url]
        source = source_dir / urllib.parse.urlparse(preview_url).path.rsplit("/", 1)[1]
        legacy = source_dir / (ident + ".mp3")
        if not source.exists() and legacy.exists() and old.get("download") == preview_url:
            data = legacy.read_bytes()
            if hashlib.sha256(data).hexdigest() == old.get("originalSha256"):
                source.write_bytes(data)
        if not source.exists():
            source.write_bytes(get(preview_url))
        output = audio_dir / (ident + ".mp3")
        levels = normalize_audio(source, output)
        author = urllib.parse.unquote(urllib.parse.urlparse(page_url).path.split("/")[2])
        duration = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                         "format=duration", "-of", "default=nw=1:nk=1", str(output)]))
        catalog.append({"id": ident, "name": name, "english": english, "category": category,
                        "caption": caption, "image": f"assets/images/{ident}.png", "audio": f"assets/audio/{ident}.mp3",
                        "duration": round(duration, 1), "loudness": levels, "credit": {"title": title, "author": author,
                        "source": page_url, "download": preview_url,
                        "license": license_name, "licenseUrl": license_url,
                        "changes": "Downloaded the public high-quality MP3 preview; first 15 seconds maximum, selected the strongest source channel, padded clips shorter than one second, two-pass normalization to -20 LUFS, peak limiting and mono MP3 conversion. Loudness verified and corrected after MP3 export.",
                        "originalSha256": hashlib.sha256(source.read_bytes()).hexdigest()}})
        print(f"Ready: {ident} ({duration:.1f}s), {levels['integratedLufs']} LUFS, {levels['truePeakDbtp']} dBTP; {license_name}", flush=True)
    (ROOT / "catalog.js").write_text("globalThis.SOUND_CATALOG = " + json.dumps(catalog, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")


if __name__ == "__main__":
    main()
