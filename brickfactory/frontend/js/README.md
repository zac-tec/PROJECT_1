# Frontend JavaScript

Current pages and service worker load:

- `api-security1.js`: shared API, navigation, dialogs and safe rendering.
- `admin-security1.js`: admin page.
- `manager-security1.js`: manager page.
- `dashboard-security1.js`: dashboard.
- `recovery.js`: session and draft recovery.
- `pwa.js`: installation/service-worker support.
- `mock-api.js`: redesign-branch-only local data layer; it keeps the prototype interactive without contacting the Pi API.

Edit the scripts referenced by HTML, and update HTML/service-worker versions together when releasing. Retired unversioned and recovery1 copies remain only on the Pi for previously cached pages; they are excluded from the fresh repository. Do not switch current HTML back to these older copies.

The `ui-redesign` branch loads `mock-api.js` after `api-security1.js`. Use
`demo` for the username and any non-empty password when previewing the UI.
This mock layer must not be merged into the production branch.
