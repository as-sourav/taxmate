# Notification inbox

TaxMate’s top bar gains a bell for the signed-in user. It lists unread Frappe Notification Logs and open ToDos, and it can mark the user’s own Notification Logs read. Open ToDos stay open until the existing filing jobs close them.

The SPA calls only methods published by `taxmate.api.get_catalog()`. Desk notification methods and `taxmate.api.resource` on Notification Log stay unused.

## Outcome

A user opening the bell sees their own unread notifications and open tasks for the active company, in English or Arabic. Marking a notification read removes it from the list. A task row opens the TaxMate document when that document has a detail screen. A guest, another user, and another company do not appear in the payload.

## API

Module: `taxmate/api/notifications.py`. Every method is `@frappe.whitelist()` with guest access left off, and the first line is `require_login()` from `taxmate.api.resource`.

Catalog entries, added in `taxmate/api/__init__.py` and mirrored as `METHOD` keys in `frontend/src/lib/frappe.ts`:

| Catalog name | Method |
|---|---|
| `list_inbox` | `taxmate.api.notifications.list_inbox` |
| `mark_read` | `taxmate.api.notifications.mark_read` |
| `mark_all_read` | `taxmate.api.notifications.mark_all_read` |

### `list_inbox`

No arguments. Returns:

```json
{
  "unread": 2,
  "has_more": false,
  "items": [
    {
      "id": "log:NAME",
      "kind": "log",
      "name": "NAME",
      "title": "Plain text",
      "created": "2026-10-22 09:00:00",
      "document_type": "UAE ESR Filing",
      "document_name": "ESR-0001",
      "route": "/esr/ESR-0001",
      "can_mark_read": true
    }
  ]
}
```

`kind` is `log` or `todo`. `id` is `log:<name>` or `todo:<name>`. `can_mark_read` is true only for `log`. `document_type`, `document_name`, and `route` are null when the row has no linked document or the DocType has no TaxMate detail route. `created` is the Frappe `creation` datetime string.

Sources, each ordered by `creation desc`, with no row cap before filtering:

- Notification Log where `for_user` is `frappe.session.user` and `read` is 0. Fields read: `name`, `subject`, `creation`, `document_type`, `document_name`.
- ToDo where `allocated_to` is `frappe.session.user` and `status` is `Open`. Fields read: `name`, `description`, `creation`, `reference_type`, `reference_name`.

Both source queries use `frappe.get_all` and pass the user filter explicitly. Linked-document checks use `frappe.get_list`, which applies read permission.

A row whose linked document fails the company check below is omitted entirely. A row with no linked document is kept.

Company check, same rule as `taxmate.api.search._in_active_company`:

- Active company comes from `get_default_company()`.
- When that value is empty, the company check keeps every permitted document.
- When `owning_company_field(doctype)` is missing, the document is kept if `get_list` returns it.
- When the company link is mandatory, `get_list` filters that field to the active company.
- When the company link is optional, `get_list` is called without a company equality filter so the existing permission query keeps this company and untagged rows.
- A name `get_list` does not return is dropped.

After filtering, rows are merged by `created` descending. `unread` is the size of the full filtered merge, so the badge matches the rows the user is allowed to see. `items` is the first 20. `has_more` is true only when that merge is longer than 20. A cap before the company check would hide an older row for the active company behind newer rows for another company, and it would leave `has_more` true after every one of those other rows had been skipped.

Title text:

- A log uses `subject`. A ToDo uses `description`.
- `frappe.utils.strip_html` runs first.
- Every `http://` and `https://` URL is removed, including the Desk form URL the reminder jobs append.
- Whitespace collapses to single spaces, then the string is trimmed.
- Longer than 180 characters becomes the first 179 characters plus `…`.

The response never includes `email_content`, `link`, `attachment_link`, `attached_file`, or the raw ToDo description.

`route` comes from `doc_route(doctype, name)` in `taxmate.api.spa_routes`. That module owns the map now living as `_SPA_DOC_ROUTES` and `_doc_route` in `taxmate/api/search.py`. Search imports it and keeps today’s routes, including percent-encoding of the document name. This change adds no routes. A DocType absent from the map yields `route: null`. The value never starts with `/app`.

### `mark_read(name)`

`name` is one Notification Log name. Load `for_user` with `frappe.db.get_value`. When the row is missing or `for_user` is not the session user, raise `frappe.PermissionError` with `_("Not permitted")`. Both cases use that same message.

When the log has a linked document, the document must pass the same visibility check as `list_inbox`. Failure raises the same `PermissionError`.

On success, set `read` to 1 with `update_modified=False`. An already-read log owned by the user, whose document is still visible, returns success without a second write. Return `{"name": "<name>", "read": 1}`.

This method does not accept a ToDo name.

### `mark_all_read`

Select every Notification Log `list_inbox` would keep, using the same user, read, permission, and company checks, including rows past the 20-item display window. Set `read` to 1 on those names only. ToDos are left open. Logs that fail the company or permission check stay unread, so switching company does not wipe unseen items.

Return `{"marked": <n>}`. `marked` is the number of logs updated.

## Panel

File: `frontend/src/components/Notifications.tsx`. `AppShell` renders `<Notifications />` inside `.tools`, before the language button. The component owns its provider. `AppShell` does not subscribe to inbox data.

The provider is the only module that calls `useFrappeGetCall` and `useFrappePostCall`. Context value is `{ state, actions, meta }`:

- `state`: `open`, `items`, `unread`, `hasMore`, `loading`, `error`
- `actions`: `toggle`, `close`, `markRead`, `markAllRead`, `refresh`
- `meta`: bell button ref and the panel id

The SWR key is `inbox:${session.company ?? ""}` from `useSession()`, so a company switch cannot keep the previous company’s rows. `refreshInterval` is 60000. `revalidateOnFocus` is true. Opening the panel calls `refresh`.

Pieces, composed by `Notifications` rather than boolean props on one component:

- `Bell` — bordered `.iconbtn`, 44px hit target on the phone breakpoint already used by `.iconbtn`.
- `Panel` — non-modal dialog.
- `List`, `Empty`, `Error`, `Skeleton` — one of these fills the panel body.

Bell accessible name is `t("a11y.notifications")` when `unread` is 0, and that string plus the unread count when `unread` is greater than 0. The numeric badge renders only when `unread` is greater than 0. Its text is `9+` when `unread` is greater than 9; the accessible name keeps the real count.

The panel anchors with `inset-inline-end: 0` and uses the user-menu surface tokens: `--surface`, `--border-2`, 12px radius, shadow `0 12px 40px rgba(0,0,0,.18)`. Width stays within `calc(100vw - 24px)`. Max height is `min(420px, 70vh)` with the list scrolling inside. Styles go in `frontend/src/styles/app.css`. There is no entrance animation.

A row shows `title` and a relative time from `Intl.RelativeTimeFormat(getLocale(), { numeric: "auto" })`, with `getLocale` from `frontend/src/lib/i18n.ts`. A row with `route` is a React Router link; activating it closes the panel. A row without `route` is text. A `log` row has a separate “Mark read” button. “Mark all read” is in the header only when some visible item has `can_mark_read`. When `hasMore` is true, the footer reads “Showing the latest 20.”

Mark-read and mark-all update the SWR cache in place. Mark-read drops that log row and subtracts one from `unread`. Mark-all drops every visible log row and sets `unread` to the number of ToDo rows still shown. A failed call restores the previous cache and sets `error`.

Empty body copy: title “You’re up to date.”, line “Deadline reminders and mentions show up here.” Error copy: “Couldn’t load notifications.” with a Retry button that calls `refresh`, on an element with `role="alert"`. The first load, while `items` is empty and `loading` is true, shows three skeleton rows and `aria-busy="true"`.

Keyboard and pointer:

- Escape closes the panel and moves focus back to the bell.
- A pointer down outside the bell and panel closes it.
- Tab closes the panel, matching the account menu, so focus continues along the top bar.
- Arrow Up and Arrow Down move between row tab stops. Home and End move to the first and last row.

Strings live in both `en` and `ar` blocks of `frontend/src/i18n/strings.ts`:

| Key | English | Arabic |
|---|---|---|
| `a11y.notifications` | Notifications | الإشعارات |
| `a11y.unread` | {n} unread | {n} غير مقروء |
| `inbox.emptyTitle` | You're up to date | لا جديد لديك |
| `inbox.emptyBody` | Deadline reminders and mentions show up here. | تظهر هنا تذكيرات المواعيد والإشارات. |
| `inbox.error` | Couldn't load notifications. | تعذر تحميل الإشعارات. |
| `inbox.retry` | Retry | إعادة المحاولة |
| `inbox.markRead` | Mark read | تعليم كمقروء |
| `inbox.markAll` | Mark all read | تعليم الكل كمقروء |
| `inbox.latest` | Showing the latest 20. | عرض أحدث ٢٠. |

## Tests

New module `taxmate/tests/test_notifications.py`, run with:

`bench --site taxmate.site run-tests --module taxmate.tests.test_notifications`

Cases:

- Guest calls to all three methods raise `frappe.AuthenticationError`.
- User A’s `list_inbox` omits user B’s Notification Log and ToDo.
- `mark_read` on B’s log, as A, raises `PermissionError` and leaves `read` at 0.
- `mark_read` on a missing name raises `PermissionError`.
- `mark_read` on A’s log sets `read` to 1, and a following `list_inbox` omits it.
- `mark_all_read` as A marks A’s visible logs and leaves B’s log unread.
- A ToDo description that contains a Desk URL is returned without that URL.
- A Notification Log subject that contains HTML tags is returned as plain text.
- A linked document whose company is not the active company is omitted. Build it the way `taxmate/tests/test_company_switcher.py` switches the active company.
- `mark_all_read` leaves a log for the other company unread.
- `get_catalog()["actions"]` contains `list_inbox`, `mark_read`, and `mark_all_read`.
- The route for an `UAE ESR Filing` row is `/esr/<encoded name>` and does not contain `/app`.

The frontend has no component test runner. After the UI exists, `npx tsc --noEmit` passes, and a browser pass covers: open the bell, empty state, error plus Retry, mark one read, mark all read, and the Arabic layout with `dir="rtl"`.

## Out of scope

Realtime sockets, a new DocType, email bodies, closing or dismissing ToDos, toasts, and any link to Desk `/app/`.
