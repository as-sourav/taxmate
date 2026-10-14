# Phase A — Audit (TaxMate phone UX)

Branch: `mobile-ux-overhaul`. No product code changes in this phase.

## §0 confirmation (from files)

| Claim | Evidence | Verdict |
|---|---|---|
| One React 18 + Vite + TS SPA (`frappe-react-sdk`, React Router) | `frontend/package.json`, `frontend/src/main.tsx`, `frontend/src/App.tsx` | Confirmed |
| Web at `/taxmate`, cookie + CSRF from `taxmate/www/taxmate.py` | `taxmate.py` redirects Guest; injects `csrf_token` / `site_name`; `main.tsx` `BrowserRouter basename="/taxmate"` | Confirmed |
| Phone Capacitor: same screens, `Authorization: TaxMate <token>`, basename `/` | `mobile/boot.tsx`, `MobileRoot.tsx` `basename="/"`, `platform.ts` `__TAXMATE_MOBILE__` | Confirmed |
| `frontend/src/mobile/` is native shell only | `boot.tsx`, `MobileRoot.tsx`, PIN/biometrics/storage modules | Confirmed |
| `__TAXMATE_MOBILE__` false in web build | `vite.config.ts` `define: { __TAXMATE_MOBILE__: JSON.stringify(mobile) }` | Confirmed |
| `MOBILE_SHELL_QUERY` = `(max-width: 900px)` | `MobileNav.tsx:31` `useIsMobileShell` | Confirmed |
| `PHONE_QUERY` = `(max-width: 760px)` | `useMedia.ts:12` `useIsPhone` | Confirmed |
| `.app.has-mnav` when mobile shell | `AppShell.tsx:96` | Confirmed |
| Phone CSS files | `shell-mobile.css`, `list-mobile.css`, `form-mobile.css`, `phone-fixes.css` | Confirmed |
| `app.css` shared — do not edit for this task | Imported globally; rail sticky there | Confirmed (constraint) |
| Tabs: Home / Sales→`/invoices` / Money→`/payments` / Reports / More | `MobileNav.tsx:38-43` | Confirmed |
| More = searchable sheet of `buildNav()` entries after AppShell filters | `MobileNav` + `AppShell:68-78` | Confirmed |
| Feature flags via `taxmate.api.settings.get_feature_flags`, fail-open | `nav.ts:158-177`, `AppShell:61-67` | Confirmed |
| Team via `canViewTeam`; POSNext via `canOpenPosNext` | `roles.ts:150-168`, `AppShell:68-78` | Confirmed |
| Report header sticky everyone; first-col pin phone only | `reports.css:373-374`; `phone-fixes.css:54-74` | Confirmed |
| Layout follows breakpoints, not `isNative()` | Grep: `useIsPhone` / `useIsMobileShell` drive layout; `isNative` for Desk links, camera, logout, etc. | Confirmed |

**Correction vs §0 wording:** Report styles live at `frontend/src/screens/reports/reports.css` (not `frontend/src/styles/reports.css`).

## Entry points

| File | Role |
|---|---|
| `frontend/src/main.tsx` | Web: mount + `BrowserRouter basename="/taxmate"`; native dynamic-imports `mobile/boot` |
| `frontend/src/App.tsx` | Routes, auth gate, session, CSRF banner (web) |
| `frontend/src/components/AppShell.tsx` | Rail vs MobileNav, feature flags, Team filter, `.has-mnav` |
| `frontend/src/mobile/boot.tsx` | Native shell entry → `MobileRoot` |

## Desktop vs phone selection

1. **≤900px:** `useIsMobileShell()` → rail unmounted, `MobileNav` mounted, `.app.has-mnav`, `.page.mnav-pad`.
2. **≤760px:** `useIsPhone()` → DataTable cards, FilterBar sheet, PageHead → `.pact-bar`, LineItems phone layout, some report/dashboard tweaks.
3. **760–900:** Mobile shell + still tables (not cards).
4. **≥901:** Desktop rail; phone CSS under `.has-mnav` inert.

## Shared components (guard if touched)

- `AppShell.tsx`, `nav.ts`, `DataTable.tsx`, `filters.tsx`, `ui.tsx` (`PageHead`, Loading/Empty/Error), `LineItems.tsx`
- `ReportDataTable.tsx` + `screens/reports/reports.css`
- Screens under `frontend/src/screens/**` that use those primitives
- Also phone-aware: `Dashboard.tsx`, `AccountantDashboard.tsx`, `ReportList.tsx`, `ReportRunner.tsx`, `JournalEntryForm.tsx`

## Phone-only (safest)

`MobileNav.tsx`, `shell-mobile.css`, `list-mobile.css`, `form-mobile.css`, `phone-fixes.css`

## Nav filtering (AppShell order)

1. `buildNav(flags)` — feature packs fail-open if key missing; `enable_pos_next` fail-closed (`!!flags.enable_pos_next`)
2. Drop `nav.posNext` unless `canOpenPosNext(session)`
3. Drop Team (+ section `nav.company` when filtering Team away) unless `canViewTeam`

## Baseline commands

| Command | Result | Notes |
|---|---|---|
| `cd frontend && npx tsc --noEmit` | **PASSED** (exit 0) | Clean |
| `cd frontend && npm run build` | **PASSED** (exit 0) | Chunk size warning only (>500kB) |
| Browser / Vite | See below | |

### Browser / Vite notes

- `npm run dev` starts at `http://127.0.0.1:5173/assets/taxmate/frontend/`.
- Vite `server.proxy` matches `^/assets`, so the Vite base path is shadowed by the bench proxy → SPA HTML/HMR not usable at that URL without config change (out of scope; not changing proxy in Phase A).
- Bench `http://localhost:8001/taxmate` with Administrator session serves the **same** built SPA + CSRF. Used for inventory screenshots.
- Capacitor device/emulator: **SKIPPED** (not available).

## Screen inventory (grouped)

### Home (owner / accountant / clients)

- **Purpose:** Role dashboards (`Dashboard` → owner / accountant / clients via `DashSwitch`).
- **Roles:** Owner → owner view; Accountant → books + owner + clients; Clerk/Viewer → accountant books view.
- **Problems:** Dense KPI grids and charts squeeze at 360; CaptureDesk in topbar competes with search; primary CTAs may sit under tab bar if not in `.pact-bar`.

### Sales lists + invoice create/detail/form

- **Purpose:** Customers, orders, quotations, DN, invoices; Sales tab lands `/invoices`.
- **Roles:** Clerk daily; Viewer read-only (`canWrite`).
- **Problems:** Cards OK ≤760; 768 still tables (wide); form line items still heavy; More sheet duplicates Sales destinations already in tab family.

### Money (payment, receivable)

- **Purpose:** Payments tab `/payments`; receivables/payables; purchase docs also in `MOBILE_TAB_PATHS.money`.
- **Roles:** Clerk payments; Accountant AR/AP.
- **Problems:** Payment create segmented controls historically overflowed (mitigated in `phone-fixes.css`); purchase mixed into Money tab highlight vs Purchase section in More.

### Purchase list

- **Purpose:** Suppliers, PO, PR, incoming/purchase invoices — Purchase in More; paths also in Money tab family.
- **Roles:** Clerk + Accountant.
- **Problems:** Tab highlight says Money while browsing purchase docs; entry discoverability depends on More search.

### Reports runner

- **Purpose:** `/reports` list + `ReportRunner` wide grids.
- **Roles:** Accountant primary; Viewer read.
- **Problems:** First-column sticky pin (`phone-fixes.css:54-74`) fights horizontal scroll (Phase E); page must not overflow — only `.rpt-dt` scrolls.

### More sheet

- **Purpose:** Full `buildNav()` after filters; search EN/AR; focus trap; closes on nav.
- **Roles:** All with app permission; Team/POS gated.
- **Problems:** Very long list (masters, setup, packs) — hard to scan; icon + label grid noise; duplicates primary tab targets (Dashboard, Invoices, Payments, Reports).

### Company / team

- **Purpose:** `/company`, `/team` under Company section.
- **Roles:** Team owner/accountant only; company settings owner/accountant (field-level).
- **Problems:** Setup-heavy on phone; candidates for desktop-oriented hide in Phase B (URL kept).

## Workflow traces (code-backed; browser confirmation in LOG)

1. Home → open invoice → back — Home tab.
2. Sales tab → invoices list → open one — Sales lit.
3. Money tab → payments — Money lit.
4. Reports → open report → horizontal scroll — Reports lit; first col pinned today.
5. More → journals or VAT 201 → back to tab — More closes; journals is in Money family → Money lit.

## Browser observations (Administrator, bench `/taxmate`)

- ≤900: rail absent; Home / Sales / Money / Reports / More present.
- ≤760: invoice list is `.lm-card`s; `.pact-bar` (“New sale”) sits above tab bar and can cover list rows until scrolled.
- More sheet title “Everything else”; dense two-column icon grid; includes Dashboard + tab destinations + all masters/packs.
- Trial Balance on phone: first column `position:sticky` (Phase E target); horizontal scroll inside `.rpt-dt` only.
- 1280/1440: rail + tables; desktop regression baselines saved under `screenshots/baseline/`.
- Signed in as Administrator (Owner dashboard). Clerk / Viewer / Accountant users: not available this session (**assumption**).

## Assumptions logged

- Clerk/Accountant/Viewer daily jobs inferred from roles + nav; not re-validated with production users this phase.
- Highest-value Phase D targets: More sheet density (hide desktop-oriented / redundant), report first-col unpin (E), topbar density at 360 — prefer tightening More over redesigning dashboards.
