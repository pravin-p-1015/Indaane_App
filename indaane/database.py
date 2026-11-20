import sqlite3
import threading
import uuid
import math
from datetime import date, datetime, timezone

from .config import BACKUPS, DB, DEMO_DB
from .security import password_hash

LOCK = threading.RLock()
DEMO_MODE = False
ACTIVE_DB = None

def set_demo_mode(enabled):
    global DEMO_MODE, ACTIVE_DB
    DEMO_MODE = bool(enabled)
    ACTIVE_DB = None
    if DEMO_MODE:
        ACTIVE_DB = DEMO_DB


class ClosingConnection(sqlite3.Connection):
    """Make SQLite context-manager usage commit/rollback and always close."""

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, salt TEXT NOT NULL, role TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS user_employee_links(user_id TEXT PRIMARY KEY REFERENCES users(id), employee_id TEXT UNIQUE NOT NULL REFERENCES employees(id));
CREATE TABLE IF NOT EXISTS employees(id TEXT PRIMARY KEY, name TEXT NOT NULL, contact TEXT DEFAULT '', daily_wage REAL NOT NULL DEFAULT 0, joined TEXT DEFAULT '', active INTEGER NOT NULL DEFAULT 1, notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS vendors(id TEXT PRIMARY KEY, name TEXT NOT NULL, contact TEXT DEFAULT '', notes TEXT DEFAULT '', active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS cylinders(id TEXT PRIMARY KEY, name TEXT NOT NULL, capacity TEXT DEFAULT '', category TEXT NOT NULL DEFAULT 'Retail', sell_price REAL NOT NULL DEFAULT 0, buy_price REAL NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, employee_id TEXT NOT NULL REFERENCES employees(id), work_date TEXT NOT NULL, vehicle TEXT DEFAULT '', opened_at TEXT NOT NULL, closed_at TEXT, opening_full TEXT NOT NULL DEFAULT '{}', closing_full TEXT NOT NULL DEFAULT '{}', closing_empty TEXT NOT NULL DEFAULT '{}', closing_damaged TEXT NOT NULL DEFAULT '{}', expected_cash REAL, actual_cash REAL, discrepancy TEXT DEFAULT '', verified_by TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'open', UNIQUE(employee_id,work_date));
CREATE TABLE IF NOT EXISTS inventory(id TEXT PRIMARY KEY, cylinder_id TEXT NOT NULL REFERENCES cylinders(id), condition TEXT NOT NULL, location TEXT NOT NULL, quantity INTEGER NOT NULL, source TEXT NOT NULL, reference TEXT, actor TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sales(id TEXT PRIMARY KEY, session_id TEXT REFERENCES sessions(id), employee_id TEXT REFERENCES employees(id), sale_date TEXT NOT NULL, kind TEXT NOT NULL, amount REAL NOT NULL, collected REAL NOT NULL, expected_return TEXT DEFAULT '', due_date TEXT DEFAULT '', created_at TEXT NOT NULL, actor TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sale_items(id TEXT PRIMARY KEY, sale_id TEXT NOT NULL REFERENCES sales(id), cylinder_id TEXT NOT NULL REFERENCES cylinders(id), quantity INTEGER NOT NULL, unit_price REAL NOT NULL, empty_quantity INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS pending_returns(id TEXT PRIMARY KEY, sale_id TEXT NOT NULL REFERENCES sales(id), employee_id TEXT REFERENCES employees(id), cylinder_id TEXT NOT NULL REFERENCES cylinders(id), quantity INTEGER NOT NULL, returned INTEGER NOT NULL DEFAULT 0, due_date TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'open');
CREATE TABLE IF NOT EXISTS cash(id TEXT PRIMARY KEY, session_id TEXT REFERENCES sessions(id), employee_id TEXT REFERENCES employees(id), kind TEXT NOT NULL, amount REAL NOT NULL, category TEXT DEFAULT '', note TEXT DEFAULT '', actor TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS vendor_tx(id TEXT PRIMARY KEY, vendor_id TEXT NOT NULL REFERENCES vendors(id), tx_date TEXT NOT NULL, note TEXT DEFAULT '', amount REAL NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS vendor_items(id TEXT PRIMARY KEY, tx_id TEXT NOT NULL REFERENCES vendor_tx(id), cylinder_id TEXT NOT NULL REFERENCES cylinders(id), kind TEXT NOT NULL, quantity INTEGER NOT NULL, unit_price REAL NOT NULL);
CREATE TABLE IF NOT EXISTS vendor_payments(id TEXT PRIMARY KEY, vendor_id TEXT NOT NULL REFERENCES vendors(id), amount REAL NOT NULL, payment_date TEXT NOT NULL, method TEXT DEFAULT '', reference TEXT DEFAULT '', note TEXT DEFAULT '', actor TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS wages(id TEXT PRIMARY KEY, employee_id TEXT NOT NULL REFERENCES employees(id), session_id TEXT REFERENCES sessions(id), work_date TEXT NOT NULL, amount REAL NOT NULL, paid REAL NOT NULL DEFAULT 0, paid_on TEXT DEFAULT '', note TEXT DEFAULT '', actor TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS advances(id TEXT PRIMARY KEY, employee_id TEXT NOT NULL REFERENCES employees(id), advance_date TEXT NOT NULL, amount REAL NOT NULL, reason TEXT DEFAULT '', actor TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS loan_tx(id TEXT PRIMARY KEY, advance_id TEXT NOT NULL REFERENCES advances(id), tx_date TEXT NOT NULL, amount REAL NOT NULL, method TEXT DEFAULT '', note TEXT DEFAULT '', actor TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS expenses(id TEXT PRIMARY KEY, expense_date TEXT NOT NULL, category TEXT NOT NULL, amount REAL NOT NULL, business INTEGER NOT NULL DEFAULT 1, session_id TEXT REFERENCES sessions(id), employee_id TEXT REFERENCES employees(id), note TEXT DEFAULT '', actor TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit(id TEXT PRIMARY KEY, actor TEXT NOT NULL, action TEXT NOT NULL, entity TEXT NOT NULL, entity_id TEXT, details TEXT DEFAULT '', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY, requested_by TEXT NOT NULL, request_type TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', decided_by TEXT DEFAULT '', decision_note TEXT DEFAULT '', requested_at TEXT NOT NULL, decided_at TEXT);
CREATE INDEX IF NOT EXISTS inventory_lookup ON inventory(cylinder_id,condition,location);
CREATE INDEX IF NOT EXISTS sales_date ON sales(sale_date);
"""

def connect():
    db = sqlite3.connect(ACTIVE_DB or DB, timeout=15, factory=ClosingConnection)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    return db

def now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
def uid(): return str(uuid.uuid4())
def money(v):
    try: n=float(v)
    except (ValueError, TypeError): raise ValueError("Enter a valid amount.")
    if not math.isfinite(n): raise ValueError("Enter a finite amount.")
    if n < 0: raise ValueError("Amount cannot be negative.")
    return round(n,2)
def qty(v):
    try: n=int(v)
    except (ValueError, TypeError): raise ValueError("Enter a whole-number quantity.")
    if n < 0: raise ValueError("Quantity cannot be negative.")
    return n
def audit(db, actor, action, entity, entity_id=None, details=""):
    db.execute("INSERT INTO audit VALUES(?,?,?,?,?,?,?)",(uid(),actor,action,entity,entity_id,str(details),now()))
def init_db():
    with LOCK, connect() as db:
        db.executescript(SCHEMA)
        if not db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            p,s=password_hash("admin123")
            db.execute("INSERT INTO users VALUES(?,?,?,?,?,?,?)",(uid(),"admin",p,s,"Owner",1,now()))
        defaults={"store_name":"Indaane Cylinder Store","currency":"INR","backup_folder":str(BACKUPS),"stock_adjustment_approval_threshold":"20"}
        for k,v in defaults.items(): db.execute("INSERT OR IGNORE INTO settings VALUES(?,?)",(k,v))

def rows(db, sql, args=()): return [dict(x) for x in db.execute(sql,args).fetchall()]
def scalar(db, sql, args=()):
    r=db.execute(sql,args).fetchone(); return r[0] if r else 0
def stock(db, cylinder, condition, location):
    return scalar(db,"SELECT COALESCE(SUM(quantity),0) FROM inventory WHERE cylinder_id=? AND condition=? AND location=?",(cylinder,condition,location))
def movement(db,cylinder,condition,location,delta,source,actor,reference=None):
    if not db.execute("SELECT 1 FROM cylinders WHERE id=?",(cylinder,)).fetchone(): raise ValueError("Select a valid cylinder type.")
    if delta < 0 and stock(db,cylinder,condition,location) < -delta:
        raise ValueError(f"Insufficient {condition.lower()} stock at {location.lower()}.")
    db.execute("INSERT INTO inventory VALUES(?,?,?,?,?,?,?,?,?)",(uid(),cylinder,condition,location,delta,source,reference,actor,now()))

