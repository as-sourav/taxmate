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

## Phase B–G

_(filled as phases complete)_
