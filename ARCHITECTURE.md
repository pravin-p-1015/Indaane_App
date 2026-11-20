# Application boundaries

`app.py` is the executable entry point. The `indaane` package separates transport, use-case orchestration, persistence, authentication, reporting, backup, and document formatting.

| Module | Responsibility |
|---|---|
| `indaane.web` | HTTP routing, request/response formatting, and server startup |
| `indaane.services` | Application use cases and transaction-scoped dispatch |
| `indaane.database` | SQLite schema, connection setup, and persistence helpers |
| `indaane.security` | Password hashing and authenticated session lifecycle |
| `indaane.reports` | Dashboard and report queries |
| `indaane.backups` | SQLite backup creation and scheduled backup loop |
| `indaane.pdf` | CSV and PDF serialization |
| `indaane.ui` | Browser interface markup and client workflows |
| `indaane.config` | Filesystem and database locations |

## SOLID decisions

- **Single responsibility:** HTTP, authentication, database setup, reporting, backups, and PDF formatting live in separate modules.
- **Open/closed:** New report formats can be added in the reporting/serialization layers without putting report SQL into the HTTP handler.
- **Liskov substitution:** The design uses injected collaborators rather than inheritance hierarchies, so subclasses are not used to vary core behavior.
- **Interface segregation:** Services receive only the small callables they need: a connection factory, a transaction lock, or an audit writer.
- **Dependency inversion:** `StoreService` and `AuthenticationService` receive their database connection factory and lock at construction; the HTTP handler calls those services rather than owning SQL transactions.

Business changes should enter through `StoreService`; reports should be added through `reports.py`; persistence should remain behind the database module. Keep browser and HTTP code free of direct business SQL.
