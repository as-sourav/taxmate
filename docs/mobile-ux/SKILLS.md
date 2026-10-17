# Skills opened for TaxMate mobile UX

Priority when skills conflict: task ground rules > TaxMate tokens / phone CSS > Frappe skills > a11y > aesthetic guidance.

| Skill | Path | Rules applied |
|---|---|---|
| Project rule: react-frontend | `.cursor/rules/react-frontend.mdc` | React + frappe-react-sdk only; no Vue/Frappe UI; catalog contract; `en`/`ar-AE` + `dir`; no hardcoded AED |
| Project rule: frappe-react-audit | `.cursor/rules/frappe-react-audit.mdc` | Fail if SPA bypasses `taxmate.api.get_catalog()`; no Desk `/app/` links; no child-table `get_list`; submit via workflow API |
| frappe-frontend-development | `~/.cursor/skills/frappe-frontend-development/SKILL.md` | Same-origin session / CSRF; Vite proxy for `/api`; no second data library; stack override: React + frappe-react-sdk (skill text is Vue-oriented) |
| frappe-ui-patterns | `~/.cursor/skills/frappe-ui-patterns/SKILL.md` | Shell + list + form + empty/error; URL-backed filters; reuse More sheet / FilterBar |
| frappe-api-development | `~/.cursor/skills/frappe-api-development/SKILL.md` | No new API surface; presentation-only nav hiding; server still enforces permission |
| vercel-react-best-practices | `.cursor/skills/vercel-react-best-practices/SKILL.md` + `rules/rerender-derived-state.md` | Keep `useMedia` boolean matchMedia; SWR via frappe-react-sdk sole cache; no continuous width subscriptions |
| vercel-composition-patterns | `.cursor/skills/vercel-composition-patterns/SKILL.md` | Do not grow boolean-prop APIs on shared components; prefer phone CSS / existing hooks |
| web-design-guidelines | `.cursor/skills/web-design-guidelines/SKILL.md` + `guidelines.md` | Icon-only → `aria-label`; ≥44px targets; labels + real input types; sticky chrome must not cover focused field |
| frontend-design | `.cursor/skills/frontend-design/SKILL.md` | Keep TaxMate tokens; do not genericize UI |
| ui-ux-pro-max | `~/.cursor/skills/ui-ux-pro-max/SKILL.md` | Touch targets; one-handed reach; reuse existing bottom sheets; safe-area |
| avoid-ai-slop | **not found** | Closest: task §6 (no decorative cards/gradients) + `frontend-design` + `~/.cursor/skills/avoid-ai-writing/SKILL.md` (writing only) |
| no-ai-slop | `~/.cursor/skills/no-ai-slop/SKILL.md` | Writing skill; for UI apply task “no decorative cards / gradients / filler” |

## IDP scan hardening (2026-10-17)

Priority on conflict: `docs/idp-scan-hardening-prompt.md` > TaxMate tokens / existing CSS > Frappe skills > a11y > aesthetics.

| Skill | Applied where |
|---|---|
| frappe-api-development | `taxmate.api.idp_desk` whitelist (`run`/`get_scan`/`cancel_scan`/`save`); catalog entries; no permission bypass |
| frappe-doctype-development | `IDP Document Log` Scan fields (`file_sha256`, `pipeline_version`, …) in `apps/idp` |
| frappe-enterprise-patterns | Background enqueue on `long` queue; realtime doc room; cancel between stages |
| frappe-testing | `test_idp_desk` / IDP eval + preprocess / validator table tests |
| vercel-react-best-practices / composition-patterns | `useScan` state machine; no boolean-prop sprawl on CaptureDesk split |
| web-design-guidelines / ui-ux-pro-max | 44px targets; permission-denial copy; retake prompt; live regions on progress |
| frontend-design | Keep TaxMate look; no generic redesign of CaptureDesk |
| no-ai-slop | Copy, comments, eval baseline docs, commit messages |
| gstack | Plan eng-review locked; `/cso` `/review` `/qa` `/benchmark` on later PRs |

## Crop-before-OCR (2026-10-17)

| Skill | Applied where |
|---|---|
| frontend-design (Anthropic) | Keep TaxMate tokens; crop chrome is functional (handles, dim mask), not decorative |
| web-design-guidelines / ui-ux-pro-max | 44px corner hits; Escape cancels crop; `aria-label` on handles |
| idp-scan-hardening §1.4–1.5 | EXIF via `imageOrientation`; long edge 2400; JPEG q0.85; mild contrast; blur gate; user crop before upload |
| vercel-composition-patterns | `CropFrame` + `prepareImage` split; CaptureDesk owns draft URL lifecycle |
