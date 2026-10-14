# Mobile UX — plan

Phase A complete in `AUDIT.md`. Phase B fills nav classification and C–G detail below.

## Phase B — Information architecture (pending)

Tabs stay Home / Sales / Money / Reports / More (4 + More). Classify every `buildNav()` entry: Primary / Secondary / Desktop-oriented / Redundant.

_(filled in Phase B)_

## Phases C–G (outline; detail in Phase B)

| Phase | Scope | Isolation | Acceptance sketch |
|---|---|---|---|
| C | MobileNav / More sheet / `MOBILE_TAB_PATHS` | Phone-only files + guarded nav helpers | ≤900 new tree; ≥1280 rail baseline; flags/roles unchanged |
| D | Highest-value screens from audit | `useIsPhone` / `.has-mnav` / phone CSS | Targets ≥44; no page overflow at 360; pact-bar; no new sheets |
| E | Remove report first-col pin | `phone-fixes.css` only | First col scrolls with sheet on phone; desktop unchanged |
| F | Workflow walkthrough | Browser phone widths | Roles recorded; hidden More URLs still work |
| G | Branch audit + REPORT | Diff review | Desktop 1440 matches baseline; tsc/build green |

## Usability reasons (Phase D)

_(recorded per change)_
