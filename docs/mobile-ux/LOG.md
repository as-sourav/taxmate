# Mobile UX — verification log

## Phase A

| Check | Result | Notes |
|---|---|---|
| §0 architecture match | **PASSED** | Confirmed in AUDIT.md; report CSS path corrected |
| `npx tsc --noEmit` | **PASSED** | exit 0 |
| `npm run build` (web) | **PASSED** | exit 0; chunk size warning only |
| Vite `npm run dev` starts | **PASSED** | `http://127.0.0.1:5173/assets/taxmate/frontend/` |
| Browser via Vite HMR | **FAILED** | `/assets` proxy shadows Vite base; SPA not loadable through Vite URL |
| Browser via bench `/taxmate` | **PASSED** | Administrator session; same built SPA + CSRF |
| Screenshots 360 phone | **PASSED** | `docs/mobile-ux/screenshots/baseline/360-*.png` (home, invoices, invoice detail, payments, reports, trial balance, More) |
| Screenshots 1280/1440 desktop | **PASSED** | `1280-home.png`, `1440-home.png`, `1440-invoices.png`, `1440-report-trial-balance.png` — rail present, no mnav |
| Report first-col pin (phone) | **PASSED** (observed) | At 360: `firstPos=sticky`, `.rpt-dt` scrollW 1079 > clientW 330, `.has-mnav` |
| Report first-col pin (desktop) | **PASSED** (observed) | At 1440: header `top:0` sticky only; `insetInlineStart:auto` (no horizontal pin) |
| Capacitor device | **SKIPPED** | No emulator/device in session |
| Shared-component list | **PASSED** | Listed in AUDIT.md |
| Workflows (visual) | **PASSED** | Sales→invoices→detail; Money→payments; Reports→Trial Balance; More sheet open |

## Phase B

| Check | Result | Notes |
|---|---|---|
| Every nav key classified | **PASSED** | PLAN.md before/after table |
| Daily workflows keep phone entry | **PASSED** | Tabs + Secondary More; D items URL-only |
| Direct URLs preserved | **PASSED** | Presentation filter only |
| Plan C–G written | **PASSED** | PLAN.md |

## Phase C

| Check | Result | Notes |
|---|---|---|
| `tsc` / `npm run build` | **PASSED** | exit 0 (same as A baseline aside from chunk hash) |
| More omits R+D | **PASSED** | No Dashboard/Invoices/Payments/Reports/Company Settings/CoA; has Journals/VAT 201/Team |
| Purchase does not light Money | **PASSED** | `/purchase-orders` — no tab `current` |
| Desktop rail ≥1280 | **PASSED** | Company Settings + full Accounting still in rail |
| Focus trap / search | **PASSED** | Search focused on open; EN labels present |
| Capacitor | **SKIPPED** | No device |

## Phase D

| Check | Result | Notes |
|---|---|---|
| Topbar targets ≥44px | **PASSED** | `.has-mnav` iconbtn/scan/lang/cobtn → 44px |
| More single-column list | **PASSED** | Scannable list (see after/360-more-after.png) |
| List cards + pact-bar | **PASSED** | Existing `:has(.pact-bar)` page padding retained |
| Desktop isolation | **PASSED** | Diff only phone CSS / MobileNav / phone nav helpers |

## Phase E

| Check | Result | Notes |
|---|---|---|
| First col unpinned on phone | **PASSED** | 360: `insetInlineStart:auto` (was sticky start); `position:sticky` only from thead `top:0` |
| Header sticky kept | **PASSED** | `reports.css` unchanged |
| Desktop report | **PASSED** | 1440 rail + table; no horizontal pin |
| max-width without sticky | **PASSED** | Kept `max-width: min(52vw, 220px)` + ellipsis |

## Phase F

| Check | Result | Notes |
|---|---|---|
| Role signed in | **PASSED** | Administrator (Owner dashboard) |
| Clerk / Accountant / Viewer | **SKIPPED** | No other users available this session |
| Home → invoice → back | **PASSED** | Phase A + after rebuild |
| Sales → invoices | **PASSED** | Tab current |
| Money → payments / journals | **PASSED** | Money current on `/journals` |
| Reports → Trial Balance scroll | **PASSED** | First col scrolls with sheet |
| More → journals / VAT 201 | **PASSED** | Links present in filtered More |
| Hidden More URL `/company` | **PASSED** | Route renders (site showed “No access for your role” for this user — permission, not missing route) |
| Viewer cannot submit | **SKIPPED** | No Viewer login |

## Phase G

| Check | Result | Notes |
|---|---|---|
| Full branch diff review | **PASSED** | Only `docs/mobile-ux/**`, `nav.ts`, `MobileNav.tsx`, phone CSS |
| `tsc` / web build | **PASSED** | Re-run after C–E |
| 1440 vs baseline | **PASSED** | Rail + home layout match (after/1440-home-after.png) |
| Debug code removed | **PASSED** | None added |
| Capacitor | **SKIPPED** | — |
