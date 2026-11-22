# Sound Garden / 소리 정원

A static, touch-friendly image and sound viewer for iPhone, iPad, Android, and desktop browsers. Select a card to see a larger generated illustration, then tap Play to hear its downloaded recording. No build step, account, or application server is required.

## Run locally

From this directory:

```powershell
python -m http.server 8000 --bind 127.0.0.1
```

Open `http://localhost:8000/`. Opening `index.html` directly as a file does not support service workers. A phone cannot use the computer's localhost address; use the deployed HTTPS address for device testing.

## Publish with GitHub Pages

Upload the project files to the intended GitHub repository, preserving the `assets/` directories. In that repository, enable GitHub Pages to publish the root directory from the branch containing these files. `.nojekyll` keeps the files as plain static assets. The viewer uses relative paths and works at `https://OWNER.github.io/REPOSITORY/`.

Repository: https://github.com/LeeMyeungJun/soundviewer. This checkout is linked to that repository on the `main` branch.

## Offline behavior

On the first visit, the viewer automatically stores the page, scripts, illustrations, and MP3 recordings. Keep it open until the offline-ready message appears. Later visits and playback use Cache Storage without downloading those files again. Interrupted downloads can be retried; already stored files are retained. The credits page is also available offline.

Use the same browser on the same device. Private browsing, clearing browser data, browser storage eviction, or a changed site address can remove or bypass the cache. Persistent storage is requested when supported, but the browser controls retention. Offline use is available after successful caching, not before the first visit. Audio playback requires a tap and stops when the viewer closes or the page becomes hidden.

The service worker handles byte-range responses for cached MP3s, including Safari audio requests. All touch controls have generous hit areas. The layout adapts from two columns on phones to three on small tablets and four on wider screens, with safe-area and dynamic-height handling.

## Media and updates

- `assets/images/*.png`: generated illustrations. Prompt set: `assets/image-prompts.json`.
- `assets/audio/*.mp3`: public high-quality MP3 previews downloaded from Freesound, converted to mono MP3, volume normalized and limited to the first 15 seconds.
- `catalog.js`: item names, categories, paths, durations, source URLs, authors, licenses, and original file hashes.
- `credits.html`: visible sound attribution and license links. Modified audio retains its source license. Vehicle sounds differ by region and model.
- `tools/download_audio.py`: reproduce the sound downloads and catalog (requires Python and FFmpeg on PATH). It respects the source host's rate-limit interval.

When changing files or adding items, increment `VERSION` in `sw.js`. The next online visit installs the updated shell and downloads the revised asset set. Old caches are removed only after the new set is completely stored. Do not change media silently without changing the version.

## Checks

```powershell
node --test tests/offline.test.cjs
```

These checks exercise cached byte ranges, cache completion/retry behavior, and repository-relative paths. Actual physical iOS and Android verification remains necessary before claiming device compatibility.
