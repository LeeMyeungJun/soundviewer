# Project guidance

- Keep the viewer buildless and compatible with GitHub Pages subdirectory hosting; use relative asset and worker URLs.
- Preserve sound author, source, license, and transformation details whenever media changes.
- Include every page's dependent script and stylesheet in the service worker shell list, including the credits page, so offline navigation remains complete.
- Increment the service worker version whenever shipped application files or media change.
- Verify playback, seeking, dialog closure, first-use storage, and offline reopening on physical iOS and Android devices before claiming device verification.
- Do not rely solely on `navigator.serviceWorker.ready` for installation errors: it can remain pending; observe worker state changes so failed installation exposes a retry.
