# Indaane Cylinder Store — Phase 3

Local, offline cylinder store management application. It uses Python's standard library and SQLite; no internet connection or package installation is needed.

## Start

1. Install Python 3.10 or newer on the store computer.
2. Double-click `start.bat`, or run `python app.py` from this folder.
3. On the store computer, open [http://127.0.0.1:8765](http://127.0.0.1:8765). The command window also prints LAN URLs for other devices on the same private network.
4. Sign in with username `admin` and initial password `admin123`.
5. Change the initial password under **Settings & backup**.

The app stores one shared database on the store computer at `data/store.db`; backups are saved under `data/backups`. The host computer must stay on while other devices use the app. Writes are serialized against the shared SQLite ledger. Keep a copy of a backup on another drive. A daily backup is made while the application is running, and a manual backup is available in Settings.

To permit other devices through Windows Firewall, add an inbound TCP rule for port `8765` on the **Private** profile. Limit the remote address range to the store's local subnet when possible. The server accepts loopback, private, and link-local addresses; it does not accept public Internet addresses. Do not port-forward this app.

LAN traffic currently uses HTTP. Use it only on a trusted, private store network; passwords and session cookies are not encrypted in transit. Do not use public Wi-Fi for employee or manager sign-ins.

To stop the app, close its command window. Data remains in SQLite and is available the next time it starts.

## Included workflows

- Multi-device LAN login with salted PBKDF2 password hashes, independent sessions, and Owner, Manager, linked Employee, and Viewer roles.
- Cylinder types and prices, employees, vendors, and quantity-based inventory movement ledger.
- Employee sessions, stock issues and returns, sales, cash collections, expenses, closing reconciliation, and wage accrual.
- Exchange, new-connection, and pending-empty sales, including partial pending-return settlement.
- Vendor deliveries, separate vendor payments and advances, business expenses, employee advances and repayments.
- Inventory, sales, pending return, vendor balance, session cash, employee summary, and expense reports with CSV export.
- Audit entries and timestamped SQLite backups.

## Important

This is the first local Phase 1 release. It does not provide remote access, multi-device operation, or cloud synchronisation. Employee accounts are read-only because user accounts are not yet linked to individual employee records. The database is append oriented for stock and financial activity; use correction entries rather than changing the database directly.

The initial financial reports are operational summaries. The plan's authoritative profit calculation needs a separately approved stock valuation and cost-of-goods-sold method before it should be used for accounting.

## Phase 2 additions

- 14-day sales trend chart on the dashboard.
- Date-filtered sales, cash-discrepancy, employee-performance, and audit reports.
- Inventory adjustment history report with date filters.
- Printable employee closing statements.
- Bulk business expense import from CSV (up to 500 rows per import); use the downloadable template.
- Configurable owner approval threshold for large stock adjustments. Managers can submit and track requests; only an Owner can approve or reject.
- Existing audit history is exposed as a report, including the actor, action, record, time, and details.
- Downloadable PDF export for reports, alongside CSV export.

Inventory discrepancy visibility currently comes from the adjustment ledger; Phase 2 does not yet add a physical stock-count workflow.

Employee accounts are linked to one employee record when an Owner creates the account. Employees can view their own sessions and pending returns, enter sales and cash transactions only for their own open session, and cannot close sessions or access finance and management screens.

The application module boundaries and SOLID design decisions are documented in [ARCHITECTURE.md](ARCHITECTURE.md).
