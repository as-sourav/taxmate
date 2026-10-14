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
