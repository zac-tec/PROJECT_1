# NEO BRICKS — Public Website

The client-facing website at [neobrickskerala.com](https://neobrickskerala.com/), built with React, TypeScript, Vite and Tailwind CSS. This is separate from the factory operations app in `../brickfactory/`.

The final design uses the Rooted colour palette with rectangular photography, upright headings and the client's brick and production-yard photographs. It includes product information, sourced fly ash brick benefits, a laboratory-report link, FAQs, phone/WhatsApp enquiry links and directions.

## Run locally

Use Node.js 22.13 or newer.

```bash
npm ci
npm run dev
```

Open the local URL printed by Vite.

## Build

```bash
npm run build
npm run preview
```

The build checks TypeScript and generates `static-dist/`. This is a static website; it does not require a Node.js process on the production server, a database or API keys.

## Edit the website

| File | Purpose |
| --- | --- |
| `app/page.tsx` | Sections, copy, image references and contact links |
| `app/globals.css` | Colours, typography, responsive layouts and final industrial refinements |
| `static-entry.tsx` | React entry point; selects the final Rooted design |
| `public/assets/` | Client-provided photographs and laboratory report |
| `index.html` | Page title, description and canonical URL |
| `public/robots.txt`, `public/sitemap.xml` | Search-engine discovery |
| `components/ui/tabs.tsx`, `lib/utils.ts` | Supporting UI code from the original design comparison |

The entry point hides the original comparison controls and always renders the selected design. Some alternate-style code is retained from the design process.

## Publishing

Build locally and upload the **contents of `static-dist/`** to the public website's configured Nginx document root. Upload assets before replacing `index.html` so a visitor cannot receive HTML pointing to missing files. Keep a rollback copy of the previous release.

Publish only to the public website. The operations app is a separate service and needs no restart for a static website update. GitHub pushes do not automatically deploy this website.

For deployment under a different domain, update the canonical URL, sitemap and contact details as appropriate. The current site assumes deployment at the domain root.

## Scope and ownership

Enquiry links open the relevant phone, email or WhatsApp application; there is no server-side contact form. The FAQ expands locally. The included photographs, branding and report belong to or were supplied for the client project; public source availability is not permission to reuse the client's identity or documents.

No environment files, server credentials, database records or hosting-provider project metadata are included in this folder.
