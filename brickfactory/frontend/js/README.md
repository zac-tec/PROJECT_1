# Frontend JavaScript

Current pages and service worker load:

- `api-security1.js`: shared API, navigation, dialogs and safe rendering.
- `admin-security1.js`: admin page.
- `manager-security1.js`: manager page.
- `dashboard-security1.js`: dashboard.
- `recovery.js`: session and draft recovery.
- `pwa.js`: installation/service-worker support.

Edit the scripts referenced by HTML, and update HTML/service-worker versions together when releasing. Retired unversioned and recovery1 copies remain only on the Pi for previously cached pages; they are excluded from the fresh repository. Do not switch current HTML back to these older copies.

The integrated UI uses real backend requests only. Demo API scripts must not be loaded or cached by production pages. Current asset/cache release: `ui-live1`.
