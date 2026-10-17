# IDP scan eval baseline

Captured before frozen-Scan / OCR-once / preprocess changes (2026-10-17).

```bash
bench --site taxmate.site execute idp.tests.eval.run_scan_eval
```

## Fixture set

15 synthetic cases in `apps/idp/idp/tests/fixtures/scan_eval/`
(clean ×4, scanned ×2, phone ×6, bilingual ×1, arabic ×1, thermal ×1).
Not yet 40+; harness accepts more `*.gt.json` pairs without API changes.

## Offline mapper baseline (ocr_text → FieldMapper)

| Metric | Value |
|---|---|
| Mode | `offline` |
| N | 15 |
| Exact-match (all header fields) | **0.0** |
| `supplier_trn` | 1.00 |
| `bill_no` | 1.00 |
| `bill_date` | 0.00 |
| `net_total` | 0.00 |
| `tax_total` | 0.93 |
| `grand_total` | 1.00 |
| `currency` | 1.00 |
| OCR passes (offline) | 0 (no `extract_content`) |
| Latency mean | ~2 ms (mapper only) |

Misses on `bill_date` / `net_total` are label/keyword gaps (`Date:` vs `invoice date`, `Net:` vs `net total`) — honest baseline, not a pass.

## TaxMate create-read OCR pass count (code audit)

`taxmate.api.idp_desk._read` for `action=create` can invoke:

1. `detect_language_isolated` (OCR)
2. `extract_content` inside `_read_with_model`
3. `extract_document` → `extract_content` again if model path returns `None`
4. `salvage_from_ocr_text` → another `extract_content`

Then `_save_create` calls `_read(..., use_model=True)` again → **another 2–4 passes**.

| Path | Typical OCR-related calls |
|---|---|
| Create read (happy hybrid) | 2–3 |
| Create read (fallback + salvage) | 3–4 |
| Save create (re-extract) | +2–4 |
| **Total user gesture** | **4–8** |

Live PNG OCR baseline (`IDP_SCAN_EVAL_MODE=live`) was not recorded in this commit (Paddle run deferred); re-run after PR3 and quote before/after here.

## Targets (from hardening brief)

- Header exact-match ≥ 95% on clean/scanned, ≥ 90% on phone photos
- Same file ×10 ⇒ identical `extracted_json`
- Review → save equals reviewed values (no re-extract)

## After / before log

| Change | Exact-match | OCR passes / read | Notes |
|---|---|---|---|
| Baseline (this file) | 0.0 offline all-fields | 2–4 read + 2–4 save | See above |
| PR2 frozen Scan + save(scan_id) | unchanged offline mapper | save: 0 OCR | no re-extract on save |
| PR3 OCR-once + async | unchanged offline | target 1 extract_content / read | poll get_scan |
| PR4 preprocess | re-run live after deploy | — | EXIF/cap/crop/deskew/CLAHE |
| PR5–PR7 | — | — | validators, camera compress, CaptureDesk split |
| PR2–PR7 shipped | see offline row above | code path 1 OCR/read | live PNG baseline still deferred |
