# Cylinder Store Management Application
## Product Requirements & Phased Development Plan

**Document version:** 1.0  
**Date:** 18 November 2026  
**Project type:** Internal business application  
**Initial deployment:** Local machine  
**Primary objective:** Build a reliable, budget-conscious cylinder store management system that can evolve through phased releases.

---

# 1. Project Overview

The application will manage the daily operations of a gas-cylinder store, including:

- Cylinder inventory and stock movements.
- Employee stock issue and return.
- Cylinder sales and pending empty-cylinder returns.
- Cash collections and expenses.
- Vendor purchases, exchanges and payments.
- Employee wages, advances and loans.
- Daily closing and financial reconciliation.
- Business reports and statistics.

The application is initially intended for internal use at the store. It does not need to be a public-facing website or customer application.

## 1.1 Core principles

1. Keep the initial implementation simple and affordable.
2. Do not introduce paid infrastructure in Phase 1.
3. All important business transactions must be traceable.
4. Do not track individual cylinder serial numbers.
5. Avoid storing unnecessary customer information.
6. Completed financial and inventory transactions must not be silently deleted or overwritten.
7. Design the database to support future upgrades.
8. Prioritise accurate stock and cash reconciliation over decorative features.

---

# 2. Release Strategy

The application will be developed in independent phases.

| Release | Main objective |
|---|---|
| Phase 1 | Local single-machine application |
| Phase 2 | Improve operations, reports and controls |
| Phase 3 | Multi-user access over the local network |
| Phase 4 | Cloud database and automatic synchronisation |
| Phase 5 | Owner's Android PWA and remote access |
| Phase 6 | Advanced reporting and automation |

Only Phase 1 is included in the initial development scope. Later phases should not delay the first usable release.

---

# 3. Phase 1 — Local Application

## 3.1 Objective

Build a complete working application that runs on one local machine at the store.

The application must work without an internet connection.

There will be:
- One local application.
- One local database.
- Local user authentication.
- Local reports.
- Local backups.

No cloud account, external server or internet connection will be required.

## 3.2 Deployment assumptions

- The application runs on a Windows or Linux machine.
- The database is stored locally.
- The application can be started and stopped by the store operator.
- Only the local machine is supported in this release.
- Data remains available after restarting the application or computer.
- Backups can be exported to another storage device.

**Important:** Phase 1 will not depend on Docker running on a remote machine or on an always-on server.

## 3.3 Proposed technology

| Component | Proposed technology |
|---|---|
| Application interface | Web-based local application |
| Backend | Python |
| Database | SQLite |
| Database access | SQLAlchemy |
| Frontend | HTML, CSS and JavaScript |
| Local server | FastAPI |
| Charts | Lightweight charting library |
| Authentication | Local application authentication |
| Packaging | Local executable or simple startup script |

These are provisional technology choices. They should be finalised before implementation.

A local web application is preferred because it provides a straightforward path to a future browser-based multi-user application.

---

# 4. Phase 1 — Functional Modules

## Module 1: Dashboard

The dashboard should provide a quick overview of the store.

Display:

- Total full cylinders.
- Total empty cylinders.
- Total damaged cylinders.
- Today's sales.
- Today's cash collections.
- Today's expenses.
- Employees currently working.
- Pending empty-cylinder returns.
- Outstanding vendor balance.
- Daily business summary.

The dashboard should not require users to navigate through multiple screens to understand the current store position.

## Module 2: Cylinder Types and Pricing

Maintain cylinder master data.

Fields:

- Cylinder name.
- Capacity or weight.
- Category: Commercial or Retail.
- Active/inactive status.
- Default selling price.
- Default purchase price.

Requirements:

- Support multiple cylinder capacities.
- Allow prices to change.
- Preserve historical prices in completed transactions.
- Allow new cylinder types to be added later.
- Do not hard-code cylinder types into application logic.

## Module 3: Inventory Management

Track cylinders by:

1. Cylinder type.
2. Category.
3. Condition.
4. Location.

Conditions:

- Full.
- Empty.
- Damaged.

Locations:

- Store.
- Employee.
- Vendor.

Inventory must be calculated from recorded stock movements.

Examples:

- Vendor to Store: Full cylinders received.
- Store to Vendor: Empty cylinders returned.
- Store to Employee: Full cylinders issued.
- Employee to Store: Remaining full cylinders returned.
- Employee to Store: Empty cylinders returned.
- Employee to Store: Damaged cylinders returned.

Requirements:

- No individual cylinder IDs.
- Quantity-based tracking.
- Prevent negative stock.
- Maintain movement history.
- Support authorised stock corrections.
- Record the person who created each transaction.

## Module 4: Employee Management

Maintain employee records.

Fields:

- Employee name.
- Contact information (optional).
- Daily wage.
- Joining date.
- Active/inactive status.
- Notes.

The application should support employees who work on different days.

## Module 5: Employee Daily Sessions

A daily session represents an employee's work for a particular day.

Opening:

- Select employee.
- Record vehicle if applicable.
- Record full cylinders issued.
- Record opening time.

During the day:

- Record sales.
- Record collected empty cylinders.
- Record pending empty returns.
- Record cash collections.
- Record expenses.

Closing:

- Record remaining full cylinders.
- Record returned empty cylinders.
- Record damaged cylinders.
- Record cash returned.
- Calculate expected cash.
- Show cash shortage or excess.
- Close the employee session.

A session should not be closed without accounting for its stock and cash, or explicitly recording an authorised discrepancy.

## Module 6: Sales Management

Support three delivery types.

### A. Exchange sale

- Full cylinder delivered.
- Empty cylinder collected.
- Sale amount recorded.
- Employee collection recorded.

### B. New connection

- Full cylinder delivered.
- No empty cylinder expected.
- Sale amount recorded.
- No pending empty return created.

### C. Pending empty return

- Full cylinder delivered.
- Empty cylinder not immediately collected.
- Outstanding empty quantity recorded against the employee.
- Expected return date recorded.

Requirements:

- Support multiple cylinder types in a sale.
- Support multiple quantities.
- Store the applicable selling price.
- Track payment collection.
- Allow partial empty-cylinder returns.
- Maintain outstanding quantities.
- Do not require customer identity.

## Module 7: Cash and Expense Management

Record employee collections and expenses.

Employee expenses may include:

- Tea and refreshments.
- Petrol.
- Vehicle maintenance.
- Other approved expenses.

Cash reconciliation:

Expected cash = Total collections - Approved expenses.

Compare expected cash with actual cash returned.

Record:

- Expected cash.
- Actual cash.
- Difference.
- Explanation.
- Person who verified the closing.

Do not automatically deduct cash shortages from employee salary.

Business expenses should be recorded separately from employee expenses. Examples include rent, electricity and other store overheads.

## Module 8: Vendor Management

Maintain vendor information and transaction history.

Vendor transactions must record:

- Empty cylinders sent.
- Damaged cylinders sent.
- Full cylinders received.
- Cylinder type.
- Quantity.
- Purchase price.
- Date and time.

Vendor payments must be recorded separately from cylinder exchanges.

Support:

- Full and partial payments.
- Advance payments.
- Outstanding balances.
- Payments made for future supplies.
- Payment method.
- Reference number.
- Notes.

The application should calculate vendor balances from recorded purchases, payments and adjustments.

## Module 9: Employee Salary and Advances

Daily wages:

- Employee.
- Work date.
- Applicable daily wage.
- Payment status.
- Amount paid.
- Payment date.

Advances and loans:

- Employee.
- Date.
- Amount.
- Reason.
- Repayment method.
- Outstanding amount.

Support salary deductions and partial repayments.

Keep wages and employee loans as separate accounting records.

## Module 10: Reports

Initial reports:

1. Current inventory.
2. Inventory movement history.
3. Daily sales.
4. Employee-wise sales.
5. Employee stock reconciliation.
6. Pending empty returns.
7. Vendor transactions.
8. Vendor outstanding balance.
9. Vendor payment history.
10. Employee cash reconciliation.
11. Employee salary report.
12. Employee advance balance.
13. Business expense report.
14. Daily cash summary.
15. Estimated profit and loss.

Reports should support date filters and export to CSV or Excel where practical.

---

# 5. Phase 1 — User Roles and Security

Even though the first release runs on one machine, the application should have user accounts.

Proposed roles:

### Owner
- Full access.
- User management.
- Settings and pricing.
- Reports.
- Transaction corrections and approvals.

### Manager
- Daily store operations.
- Inventory management.
- Sales.
- Vendor transactions.
- Employee sessions.
- Cash closing.
- Reports.

### Employee
- Optional individual account.
- Access limited to permitted employee operations.

### Viewer
- Read-only access.

The permission system should be configurable rather than relying only on fixed role names.

Security requirements:

- Passwords stored using secure password hashing.
- Local session authentication.
- Permission checks on the backend.
- Audit trail for important operations.
- No direct editing of completed transactions without an authorised correction process.

---

# 6. Phase 1 — Database Design

SQLite will be the initial database.

The schema should use relational tables and stable identifiers so that migration to PostgreSQL is possible later.

## 6.1 Master tables

| Table | Purpose |
|---|---|
| users | Application users |
| roles | User roles |
| permissions | Individual permissions |
| user_permissions | User access configuration |
| employees | Employee records |
| vendors | Vendor records |
| cylinder_types | Cylinder master data |
| price_history | Historical purchase and selling prices |
| expense_categories | Expense classifications |
| vehicles | Optional vehicle records |
| business_settings | Application settings |

## 6.2 Inventory tables

| Table | Purpose |
|---|---|
| inventory_transactions | Inventory movement header |
| inventory_transaction_items | Individual cylinder movements |

Every inventory transaction should have a unique ID, timestamp, source, reference and creator.

## 6.3 Employee and sales tables

| Table | Purpose |
|---|---|
| employee_sessions | Daily employee work sessions |
| sales | Sale header |
| sale_items | Cylinder quantities and prices |
| pending_returns | Outstanding empty cylinders |
| employee_cash_transactions | Collections and expenses |

## 6.4 Vendor tables

| Table | Purpose |
|---|---|
| vendor_transactions | Vendor exchange/purchase header |
| vendor_transaction_items | Cylinder quantities and purchase costs |
| vendor_payments | Vendor payments and advances |

## 6.5 Finance tables

| Table | Purpose |
|---|---|
| employee_salary_records | Daily wages |
| employee_advances | Employee loans and advances |
| employee_loan_transactions | Repayments and deductions |
| business_expenses | General business expenses |
| cash_accounts | Cash and bank accounts |

## 6.6 System tables

| Table | Purpose |
|---|---|
| audit_log | Important user actions |
| schema_version | Database migration tracking |

The initial database should not contain unnecessary cloud synchronisation tables or remote-user workflows. Those will be introduced when needed.

---

# 7. Data Integrity and Accounting Rules

These rules apply from the first release and must be preserved in every later version.

1. Completed transactions must not be silently deleted.
2. Corrections should use reversal or adjustment transactions.
3. Every transaction must have a unique identifier.
4. Inventory must never become negative through normal operations.
5. Historical transaction prices must not change when default prices are updated.
6. Pending empty returns must support partial settlement.
7. Vendor payments must be independent of vendor cylinder purchases.
8. Employee wages and loans must be accounted for separately.
9. Cash shortages and excesses must be recorded explicitly.
10. Every important transaction must record its creator and timestamp.
11. Financial calculations must be based on transaction records, not manually maintained totals.
12. All related stock and financial updates must be committed atomically.

## Profit calculation

Do not treat vendor payments as the cost of goods sold.

Vendor payments may be advances for future supplies. Profit calculations should use the cost of the cylinders actually sold, with appropriate treatment of stock valuation and damaged stock.

The accounting method should be finalised before the profit report is considered authoritative.

---

# 8. Phase 1 — Backup and Recovery

Local data protection is essential because the application initially has only one database.

Required features:

- Manual backup.
- Automatic scheduled backup when the application is running.
- Backup to a separate folder or drive.
- Database integrity check.
- Backup history.
- Restore procedure.
- Export of important reports.

The application should warn users if recent backups are unavailable.

A backup stored only beside the live database is not sufficient protection against drive failure.

---

# 9. Phase 1 — User Interface

Proposed navigation:

1. Dashboard
2. Inventory
3. Sales
4. Employee Sessions
5. Employees
6. Pending Returns
7. Vendors
8. Vendor Payments
9. Expenses
10. Salary and Advances
11. Reports
12. Settings
13. Backup and Restore

Design priorities:

- Simple screens.
- Minimal typing.
- Large buttons for common operations.
- Clear quantity and cash displays.
- Fast data entry.
- Confirmation before completing important transactions.
- Clear warnings for insufficient stock and cash discrepancies.

The application should be usable by a store manager without technical knowledge.

---

# 10. Phase 1 — Development Sequence

Development should follow this order.

| Step | Work | Deliverable |
|---|---|---|
| 1 | Finalise business rules | Approved requirements |
| 2 | Finalise database schema | SQLite schema |
| 3 | Build authentication and permissions | Login system |
| 4 | Build master data screens | Employees, vendors, cylinder types |
| 5 | Build inventory ledger | Stock tracking |
| 6 | Build employee sessions | Stock issue and return |
| 7 | Build sales | Exchange, new connection and pending return |
| 8 | Build cash and expenses | Cash reconciliation |
| 9 | Build vendor management | Purchases and payments |
| 10 | Build salary and advances | Employee accounts |
| 11 | Build reports | Operational and financial reports |
| 12 | Build backup and restore | Data protection |
| 13 | Testing | Verified local release |
| 14 | Deployment | Local production application |

---

# 11. Phase 1 — Acceptance Criteria

Phase 1 is complete when the following scenarios work correctly.

### Inventory
- Create different cylinder types.
- Receive cylinders from a vendor.
- Issue cylinders to employees.
- Return remaining full cylinders.
- Receive empty and damaged cylinders.
- View stock by type, condition and location.
- Verify that all movements produce correct stock balances.

### Sales
- Complete an exchange sale.
- Complete a new connection sale.
- Record a pending empty return.
- Record partial pending returns.
- Verify the outstanding quantity.

### Employees
- Open a daily session.
- Issue stock.
- Record multiple sales.
- Record expenses.
- Return stock.
- Reconcile cash.
- Close the session.

### Vendor
- Record cylinders sent.
- Record full cylinders received.
- Record partial payments.
- Record an advance for future supplies.
- Verify vendor balance.

### Finance
- Record daily wages.
- Record employee advances.
- Record salary deductions.
- Record business expenses.
- Generate financial reports.

### Reliability
- Restart the application without losing data.
- Restore a backup successfully.
- Prevent duplicate submissions.
- Prevent negative inventory.
- Preserve completed transaction history.

---

# 12. Phase 2 — Operational Improvements

**Objective:** Improve the local application after real store usage.

Possible additions:

- Better dashboard and charts.
- More detailed reports.
- Printable daily closing statements.
- Employee performance reports.
- Improved cash and inventory discrepancy reports.
- Bulk data entry.
- Import/export improvements.
- Faster transaction workflows.
- More detailed audit history.
- Configurable approval workflows.

This phase should be driven by actual feedback from the store manager.

---

# 13. Phase 3 — Local Network Multi-User Access

**Objective:** Allow multiple devices to access the application inside the store.

Potential capabilities:

- Manager uses the main computer.
- Employees use phones or other computers on the local network.
- Central local database.
- Individual logins.
- Permission-based access.
- Simultaneous transaction handling.

This phase will require the local application to run as a server on the store machine.

The local machine must remain switched on while other devices are using it.

No internet or cloud account is required for local network operation.

---

# 14. Phase 4 — Cloud Database and Synchronisation

**Objective:** Introduce remote access while retaining local operation.

Proposed technology:

- Supabase PostgreSQL as the central database.
- Local SQLite database remains available.
- Automatic two-way synchronisation.
- Unique transaction IDs.
- Idempotent transaction uploads.
- Sync logs and recovery mechanisms.

Normal behaviour:

- Local transactions sync automatically when internet is available.
- Cloud transactions are downloaded automatically.
- Offline transactions remain in a local queue.
- Synchronisation resumes when connectivity returns.
- A manual Force Sync button is available as a failsafe.

The sync system must not overwrite newer remote transactions with older local data.

It must handle duplicate submissions, retries and conflicting changes safely.

The cloud database must become the shared source of truth for remote users, while the local database remains the store's operational copy.

---

# 15. Phase 5 — Owner's Android PWA

**Objective:** Give the owner remote access without requiring the store computer to run 24/7.

The owner can access the application through an Android-friendly Progressive Web App.

Owner capabilities:

- View dashboard.
- View inventory.
- View sales.
- View employee reports.
- View vendor balances.
- View expenses.
- View financial reports.
- Add vendor payment entries.

Restrictions:

- Owner's remote operational access is read-only.
- Owner cannot edit or delete existing store transactions.
- Vendor payments can be added remotely.
- Remote payments are initially marked unverified.
- Manager verifies the payment locally.
- All actions are recorded in the audit trail.

The PWA will access the cloud database directly through secure backend APIs.

The store application does not need to be running for the owner to access the latest synchronised information.

A free hosting option and provider URL should be evaluated before deployment. A paid domain is not a project requirement.

---

# 16. Phase 6 — Advanced Features

Potential future improvements:

- Automated daily and monthly reports.
- Advanced profitability analysis.
- Inventory forecasting.
- Low-stock alerts.
- Pending-return reminders.
- Vendor payment reminders.
- Employee performance trends.
- Exportable financial statements.
- Optional notifications.
- Advanced analytics.

These features are optional and should not complicate the initial release.

---

# 17. Future-Proofing Requirements

Although Phase 1 is local-only, the following design decisions should be made correctly from the beginning.

1. Use UUIDs or another stable globally unique ID for records.
2. Use database migrations rather than manually modifying production tables.
3. Store timestamps consistently in UTC and display them in local time.
4. Keep business logic separate from the user interface.
5. Use a service/API layer for database operations.
6. Keep the database relational and portable.
7. Avoid SQLite-specific features where PostgreSQL compatibility is important.
8. Keep audit information for important operations.
9. Use append-only financial and inventory ledgers.
10. Avoid hard-coded user roles and cylinder types.
11. Design transactions so they can later be synchronised independently.
12. Maintain versioned backup and restore procedures.

## Important architectural boundary

Phase 1 should not implement cloud synchronisation prematurely.

However, the database and business logic must not be tightly coupled to SQLite. This will make the later migration to PostgreSQL and multi-device operation easier.

---

# 18. Explicitly Out of Scope for Phase 1

To prevent scope creep, the following will not be implemented initially:

- Cloud database.
- Remote owner access.
- Android PWA.
- Public website.
- Paid domain.
- Paid hosting.
- Multi-device network access.
- Automatic cloud synchronisation.
- Customer database.
- Individual cylinder tracking.
- Online payment gateway.
- Third-party accounting integrations.
- AI-based analysis.

These can be considered in later releases.

---

# 19. Project Milestones

| Milestone | Expected outcome |
|---|---|
| M1 | Business requirements finalised |
| M2 | Database schema approved |
| M3 | Inventory and master data working |
| M4 | Sales and employee workflows working |
| M5 | Vendor and financial workflows working |
| M6 | Reports and dashboard working |
| M7 | Backup and restore tested |
| M8 | Phase 1 acceptance testing |
| M9 | Local production release |

No calendar estimates are assigned yet. Development effort should be estimated after the requirements and database schema are approved.

---

# 20. Final Release Strategy

The most important decision is to avoid building the entire future system in the first release.

**Phase 1 must solve the store's actual daily operational problems reliably.**

The first release should be:

- Local.
- Offline-capable.
- Easy to operate.
- Affordable.
- Secure.
- Backed up.
- Accurate in inventory and cash accounting.

Later releases will add network access, cloud synchronisation and remote owner access without requiring a complete rewrite.

**Initial development target: Phase 1 — Local Cylinder Store Management Application.**