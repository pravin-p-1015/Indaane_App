"""Create a clearly separated, synthetic workspace for product demonstrations."""
import json
import sqlite3
from datetime import date, timedelta

from . import database


def prepare_demo_database(owner):
    database.DEMO_DB.parent.mkdir(exist_ok=True)
    db=sqlite3.connect(database.DEMO_DB,timeout=15,factory=database.ClosingConnection)
    db.row_factory=sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        db.executescript(database.SCHEMA)
        initialized=db.execute("SELECT value FROM settings WHERE key='mock_data_initialized'").fetchone()
        if initialized:
            return
        db.execute("INSERT OR REPLACE INTO users VALUES(?,?,?,?,?,?,?)",tuple(owner[k] for k in ("id","username","password","salt","role","active","created_at")))
        today=date.today()
        employee_a,employee_b=database.uid(),database.uid()
        vendor=database.uid()
        cylinder_a,cylinder_b=database.uid(),database.uid()
        db.execute("INSERT INTO employees VALUES(?,?,?,?,?,?,?)",(employee_a,"Asha Rao","9000000001",850,(today-timedelta(days=400)).isoformat(),1,"Demo employee"))
        db.execute("INSERT INTO employees VALUES(?,?,?,?,?,?,?)",(employee_b,"Kiran Shah","9000000002",800,(today-timedelta(days=180)).isoformat(),1,"Demo employee"))
        db.execute("INSERT INTO vendors VALUES(?,?,?,?,?)",(vendor,"Demo Gas Supply","9000000003","Synthetic vendor record",1))
        db.execute("INSERT INTO cylinders VALUES(?,?,?,?,?,?,?)",(cylinder_a,"Domestic 14.2 kg","14.2 kg","Retail",950,780,1))
        db.execute("INSERT INTO cylinders VALUES(?,?,?,?,?,?,?)",(cylinder_b,"Commercial 19 kg","19 kg","Commercial",1750,1480,1))
        database.movement(db,cylinder_a,"Full","Store",24,"demo opening stock","DEMO")
        database.movement(db,cylinder_a,"Empty","Store",8,"demo opening stock","DEMO")
        database.movement(db,cylinder_b,"Full","Store",7,"demo opening stock","DEMO")
        database.movement(db,cylinder_b,"Empty","Store",3,"demo opening stock","DEMO")
        sale_id=database.uid()
        db.execute("INSERT INTO sales VALUES(?,?,?,?,?,?,?,?,?,?,?)",(sale_id,None,None,today.isoformat(),"exchange",950,950,"","",database.now(),"DEMO"))
        db.execute("INSERT INTO sale_items VALUES(?,?,?,?,?,?)",(database.uid(),sale_id,cylinder_a,1,950,1))
        db.execute("INSERT INTO cash VALUES(?,?,?,?,?,?,?,?,?)",(database.uid(),None,None,"collection",950,"sale","Demo counter sale","DEMO",database.now()))
        db.execute("INSERT INTO expenses VALUES(?,?,?,?,?,?,?,?,?,?)",(database.uid(),today.isoformat(),"Fuel",120,1,None,None,"Demo expense","DEMO",database.now()))
        tx_id=database.uid()
        db.execute("INSERT INTO vendor_tx VALUES(?,?,?,?,?,?,?)",(tx_id,vendor,(today-timedelta(days=2)).isoformat(),"Demo delivery",1480,"DEMO",database.now()))
        db.execute("INSERT INTO vendor_items VALUES(?,?,?,?,?,?)",(database.uid(),tx_id,cylinder_b,"received",1,1480))
        db.execute("INSERT INTO vendor_payments VALUES(?,?,?,?,?,?,?,?,?)",(database.uid(),vendor,500,(today-timedelta(days=1)).isoformat(),"UPI","DEMO-001","Demo payment","DEMO",database.now()))
        db.execute("INSERT INTO settings VALUES('mock_data_initialized','1')")
        db.execute("INSERT INTO settings VALUES('stock_adjustment_approval_threshold','20') ON CONFLICT(key) DO NOTHING")
        db.execute("INSERT INTO audit VALUES(?,?,?,?,?,?,?)",(database.uid(),"DEMO","created","mock_workspace",None,"Synthetic demonstration records initialized",database.now()))
        db.commit()
    finally:
        db.close()
