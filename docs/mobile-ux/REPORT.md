# TaxMate mobile UX — final report

Branch: `mobile-ux-overhaul` (not pushed). Phone-only changes; desktop 1280/1440 kept.

## A. Navigation

**Tabs (unchanged):** Home `/` · Sales `/invoices` · Money `/payments` · Reports `/reports` · More.

**Before:** More listed every `buildNav()` row (after flags/roles), including tab duplicates; Purchase paths lit the Money tab.

**After:**

| Class | What |
|---|---|
| **Primary** | Tab targets + Sales/Money/Reports route families (`MOBILE_TAB_PATHS`; Purchase removed from Money) |
| **Secondary** | Remaining daily docs in More (customers…VAT 201, Team, etc.) — single-column list |
| **Hidden-but-reachable (D)** | Setup/masters (CoA, tax templates, Company Settings, serial/batch, …) omitted from More; URL still works |
| **Removed from More (R)** | Dashboard, Invoices, Payments, Reports (same as tabs) |

**Why:** Shorter More, clearer tabs, no lost daily paths. Rail/`buildNav` filtering unchanged.

## B. UI

| Change | Problem solved |
|---|---|
| More → single-column list, quieter icons | Dense two-up tiles hard to scan |
| Topbar controls ≥44px under `.has-mnav` | Sub-44px chrome on phone |
| Report first column no longer sticky-start | Horizontal scroll fought the pin (Phase E) |

Lists stay cards ≤760px; reports stay tables; no new sheets/nav paradigms.

## C. Reports

- Removed first-column pin in `phone-fixes.css` (`position: sticky; inset-inline-start: 0` block).
- Kept header-row stickiness in `screens/reports/reports.css`.
- Kept `max-width: min(52vw, 220px)` + ellipsis **without** sticky.
- Desktop: no horizontal pin (unchanged).

## D. Files

| Path | Purpose |
|---|---|
| `frontend/src/lib/nav.ts` | `MOBILE_MORE_OMIT`, `filterNavForMobileMore`, Money family trim |
| `frontend/src/components/MobileNav.tsx` | Apply phone More filter |
| `frontend/src/styles/shell-mobile.css` | More list layout; 44px topbar under `.has-mnav` |
| `frontend/src/styles/phone-fixes.css` | Unpin report first column |
| `docs/mobile-ux/*` | AUDIT, PLAN, LOG, SKILLS, REPORT, screenshots |

## E. Verification

See `LOG.md`. Summary: tsc/build **PASSED**; phone More/tabs/unpin **PASSED**; Vite HMR URL **FAILED** (proxy/`/assets`); Capacitor **SKIPPED**; Clerk/Viewer logins **SKIPPED**.

## F. Desktop

Bench `/taxmate` at 1280/1440: rail present, Company Settings + full Accounting visible; compared to `screenshots/baseline/1440-*.png` and `after/1440-home-after.png`. Diff has no unguarded desktop CSS. Vite HMR not used for visual checks (proxy conflict).

## G. Assumptions

1. Desktop-oriented More hides are presentation-only; `/company` etc. stay reachable.
2. When unsure S vs D, preferred S for compliance/stock ops and D for masters/setup.
3. Only Administrator was available; Viewer submit block and Clerk UX not re-checked live.
4. `/company` rendered an access message for this user — route exists; server/UI permission separate from More hiding.
