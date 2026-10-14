# Mobile UX — plan

Phase A: `AUDIT.md`. Tabs stay **Home / Sales / Money / Reports / More** (4 + More). No new drawer or router.

## Phase B — Nav classification

`buildNav()` + AppShell filters (flags, `canViewTeam`, `canOpenPosNext`) stay the desktop rail source of truth. Phone More applies an **additional presentation filter** only.

### Tabs (unchanged targets)

| Tab | `to` | Rationale |
|---|---|---|
| Home | `/` | Owner/accountant landing |
| Sales | `/invoices` | Clerk daily invoices (audit confirmed; no retarget) |
| Money | `/payments` | Receive/make payment |
| Reports | `/reports` | Accountant reports |
| More | sheet | Everything else (filtered) |

### `MOBILE_TAB_PATHS` after

| Tab | Paths | Change |
|---|---|---|
| sales | `/customers`, `/orders`, `/quotations`, `/delivery-notes`, `/invoices`, `/leads`, `/pos-invoices` | Unchanged |
| money | `/payments`, `/receivables`, `/payables`, `/journals`, `/bank-reconciliation`, `/bank-accounts` | **Remove** purchase routes so Purchase no longer lights Money |
| reports | `/reports` | Unchanged |

Purchase / Stock / Masters / Compliance / setup light **no** tab (More active only while sheet open).

### Before → After (every link)

Legend: **P** primary (tab or family) · **S** secondary (More) · **D** desktop-oriented (hide on phone More; URL works) · **R** redundant (omit from phone More; same as a tab)

| Key | Path | Before | After | Rationale |
|---|---|---|---|---|
| nav.dashboard | `/` | More + Home | **R** | Same as Home tab |
| nav.customers | `/customers` | More + Sales family | **S** + P-family | Daily sales party |
| nav.salesOrders | `/orders` | More + Sales | **S** + P-family | Daily |
| nav.quotations | `/quotations` | More + Sales | **S** + P-family | Daily |
| nav.deliveryNotes | `/delivery-notes` | More + Sales | **S** + P-family | Daily |
| nav.invoices | `/invoices` | More + Sales tab | **R** | Same as Sales tab |
| nav.payments | `/payments` | More + Money tab | **R** | Same as Money tab |
| nav.receivables | `/receivables` | More + Money | **S** + P-family | AR follow-up |
| nav.leads | `/leads` | More + Sales | **S** + P-family | Occasional sales |
| nav.suppliers | `/suppliers` | More + Money family | **S** | Purchase; no tab light |
| nav.supplierQuotations | `/supplier-quotations` | More + Money | **S** | Purchase |
| nav.purchaseOrders | `/purchase-orders` | More + Money | **S** | Purchase |
| nav.purchaseReceipts | `/purchase-receipts` | More + Money | **S** | Purchase |
| nav.incomingInvoices | `/incoming-invoices` | More + Money | **S** | Clerk intake |
| nav.purchaseInvoices | `/purchase-invoices` | More + Money | **S** | Bills |
| nav.payables | `/payables` | More + Money | **S** + P-family | AP |
| nav.stockEntries | `/stock-entries` | More | **S** | Warehouse moves |
| nav.stockReconciliations | `/stock-reconciliations` | More | **S** | Stock ops |
| nav.materialRequests | `/material-requests` | More | **S** | Stock ops |
| nav.serialNos | `/serial-nos` | More (flag) | **D** | Lookup/setup; flag still gates rail |
| nav.batches | `/batches` | More (flag) | **D** | Same |
| nav.landedCostVouchers | `/landed-cost-vouchers` | More | **D** | Rare desktop voucher |
| nav.boms | `/boms` | More (flag) | **D** | Manufacturing setup |
| nav.workOrders | `/work-orders` | More (flag) | **S** | Shop-floor if pack on |
| nav.pickLists | `/pick-lists` | More (flag) | **S** | Fulfilment if pack on |
| nav.journals | `/journals` | More + Money | **S** + P-family | Accountant daily |
| nav.bankAccounts | `/bank-accounts` | More + Money | **S** + P-family | Cash position |
| nav.modesOfPayment | `/modes-of-payment` | More | **D** | Master setup |
| nav.bankReconciliation | `/bank-reconciliation` | More + Money | **S** + P-family | Accountant |
| nav.fiscalYears | `/fiscal-years` | More | **D** | Period setup |
| nav.accounts | `/accounts` | More | **D** | CoA tree better on desktop |
| nav.costCenters | `/cost-centers` | More | **D** | Setup |
| nav.periodClosing | `/period-closing` | More | **D** | Period close |
| nav.currencyExchanges | `/currency-exchanges` | More | **D** | FX table |
| nav.reports | `/reports` | More + Reports tab | **R** | Same as Reports tab |
| nav.items | `/catalogue/items` | More | **S** | Items used on phone |
| nav.itemGroups | `/catalogue/item-groups` | More | **D** | Taxonomy |
| nav.brands | `/catalogue/brands` | More | **D** | Taxonomy |
| nav.uoms | `/catalogue/uoms` | More | **D** | Taxonomy |
| nav.warehouses | `/warehouses` | More | **S** | Stock location |
| nav.priceLists | `/price-lists` | More | **D** | Pricing setup |
| nav.paymentTermsTemplates | `/payment-terms-templates` | More | **D** | Setup |
| nav.taxTemplates | `/tax-templates` | More | **D** | Tax setup |
| nav.taxCategories | `/tax-categories` | More | **D** | Tax setup |
| nav.itemTaxTemplates | `/item-tax-templates` | More | **D** | Tax setup |
| nav.pricingRules | `/pricing-rules` | More | **D** | Pricing setup |
| nav.customerGroups | `/customer-groups` | More | **D** | Taxonomy |
| nav.supplierGroups | `/supplier-groups` | More | **D** | Taxonomy |
| nav.territories | `/territories` | More | **D** | Taxonomy |
| nav.addresses | `/addresses` | More | **S** | Party address fix-ups |
| nav.contacts | `/contacts` | More | **S** | Party contacts |
| nav.termsAndConditions | `/terms-and-conditions` | More | **D** | Legal boilerplate |
| nav.vat201 | `/vat-201` | More | **S** | UAE filing daily path |
| nav.ct | `/ct-filings` | More | **S** | CT filings |
| nav.esr | `/esr` | More | **S** | ESR |
| nav.ubo | `/ubo` | More | **S** | UBO |
| nav.lateFilings | `/late-filings` | More | **S** | Notices |
| nav.eInvoiceLog | `/e-invoice-log` | More | **S** | E-invoice ops |
| nav.taxSettings | `/tax-settings` | More | **D** | ASP / site settings |
| nav.uaeRelatedParties | `/uae-related-parties` | More | **D** | Compliance master |
| nav.uaeVatGroups | `/uae-vat-groups` | More | **D** | Compliance master |
| nav.uaeBadDebt | `/uae-bad-debt-relief` | More | **D** | Rare adjustment |
| nav.uaeCustoms | `/uae-customs-declarations` | More | **D** | Rare |
| nav.uaeCapitalGoods | `/uae-capital-goods-adjustments` | More | **D** | Rare |
| nav.posInvoices | `/pos-invoices` | More + Sales family | **S** + P-family | If POS flag |
| nav.posProfiles | `/pos-profiles` | More | **D** | POS setup |
| nav.posNext | external | More | **S** | External POS when allowed |
| nav.loyaltyPrograms | `/loyalty-programs` | More | **D** | Program setup |
| nav.loyaltyPointEntries | `/loyalty-point-entries` | More | **S** | Point ledger if pack on |
| nav.assets | `/assets` | More | **S** | Asset list if pack on |
| nav.assetCategories | `/asset-categories` | More | **D** | Asset setup |
| nav.companySettings | `/company` | More | **D** | Wide settings form |
| nav.team | `/team` | More (role) | **S** | Invite still needed on phone for owners |

**Assumption:** When unsure between S and D, chose S for daily compliance/stock and D for masters/setup. Direct URLs always work.

### Phone More tree (after)

1. Sales — customers, orders, quotations, DN, receivables, leads _(no invoices)_
2. Purchase — full purchase list + payables
3. Stock — SE, SR, MR, work orders, pick lists _(no serial/batch/LCV/BOM)_
4. Accounting — journals, bank accounts, bank recon _(no CoA/FY/…)_ ; _(no reports)_
5. Masters — items, warehouses, addresses, contacts
6. UAE Compliance — VAT 201, CT, ESR, UBO, late filings, e-invoice log
7. POS / Loyalty / Assets — invoices/points/assets + POS Next when flagged _(no profiles/programs/categories)_
8. Company — Team only when `canViewTeam` _(no Company Settings)_

Top-level Dashboard link removed (Home tab).

---

## Phases C–G

### Phase C — Navigation

| | |
|---|---|
| **Files** | `nav.ts` (`MOBILE_TAB_PATHS`, phone More helper), `MobileNav.tsx` (filter More), `shell-mobile.css` (scan-friendly list) |
| **Change** | Apply classification; tighten Money family; More omits R+D; single-column denser text, quieter icons |
| **Isolation** | Helper used only by `MobileNav`; rail still uses unfiltered `buildNav` from AppShell |
| **Risks** | Hiding a daily path → leave in Secondary; search must still match EN/AR for remaining rows |
| **Checks** | ≤900 new More; ≥1280 rail = baseline; Team/flags/roles unchanged; focus trap/close intact |
| **Accept** | Gate C in LOG |

### Phase D — Screens

| | |
|---|---|
| **Files** | `shell-mobile.css`, `list-mobile.css`, `phone-fixes.css`, possibly guarded topbar rules under `.has-mnav` |
| **Change** | (1) More sheet scanability if not finished in C. (2) Ensure list scroll clears `.pact-bar` at 360. (3) Topbar: reduce chrome collision under `.has-mnav` without removing Search/lang/theme. |
| **Isolation** | Phone CSS / `.has-mnav` only |
| **Usability reasons** | Recorded below per change |
| **Accept** | No page overflow 360; targets ≥44; desktop untouched |

### Phase E — Report first column

| | |
|---|---|
| **Files** | `phone-fixes.css` only |
| **Change** | Remove sticky first-column block; keep optional `max-width` **without** `position: sticky` if long names blow page |
| **Keep** | Header sticky in `reports.css`; desktop unchanged |
| **Accept** | 360/390/430 first col scrolls away; 1280/1440 match baseline |

### Phase F — Workflows

Walk Home → invoice → back; Sales → invoices; Money → payments; Reports → wide report scroll; More → journals/VAT 201; open a **D**-hidden URL (e.g. `/company`) and confirm it renders; note roles available.

### Phase G — Branch audit

Full diff, tsc, web build, re-shoot 1440 home/invoices/report vs baseline, write `REPORT.md`.

---

## Usability reasons (Phase D)

| Change | Problem | Why |
|---|---|---|
| More: omit R+D + quieter list | Sheet lists ~70 destinations; duplicates tabs | Faster one-handed find of daily secondary screens |
| Money family without Purchase | Purchase lit Money tab | Tab meaning matches Money jobs |
| List/page bottom padding vs pact-bar | Invoice cards under New sale bar | Primary action stays reachable; rows remain tappable |
| Report unpin (E) | Sticky first col fights horizontal scroll | See whole sheet without fighting the pin |
