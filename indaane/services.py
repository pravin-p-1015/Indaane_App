import json
import math
import re
import sqlite3
import uuid
from datetime import date, datetime
from pathlib import Path

from . import database as database_module
from .config import BACKUPS
from .backups import create_backup
from .database import SCHEMA, audit, movement, now, qty, rows, scalar, stock, uid, money
from .pdf import csv_data, make_pdf
from .reports import dashboard, report
from .security import password_hash

def _required_text(value, label):
    value=str(value or "").strip()
    if not value: raise ValueError(f"{label} is required.")
    return value

def _valid_date(value, label):
    value=str(value or "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}",value): raise ValueError(f"Enter a valid {label} date in YYYY-MM-DD format.")
    try: return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError): raise ValueError(f"Enter a valid {label} date in YYYY-MM-DD format.")

def _dispatch(db, action, d, user):
    actor=user["username"]; role=user["role"]
    if role=="Viewer" and action not in ("list","dashboard","report","export","export_pdf","me","data_status"): raise PermissionError("Viewer access is read-only.")
    if role=="Employee":
        allowed={"me","list","report","sale","cash","return_pending","data_status"}
        if action not in allowed: raise PermissionError("This account does not have permission for that operation.")
        if not user.get("employee_id"): raise PermissionError("This account is not linked to an employee record.")
        if action=="list" and d.get("table") not in ("sessions","sales","pending_returns","cylinders"): raise PermissionError("This account cannot view that register.")
        if action=="report" and d.get("query")!="pending": raise PermissionError("This account cannot view that report.")
    if action=="me": return {"username":actor,"role":role}
    if action=="data_status": return {"mode":"demo" if database_module.DEMO_MODE else "live"}
    if action=="data_mode":
        if role!="Owner": raise PermissionError("Only the owner can switch data workspaces.")
        mode=d.get("mode")
        if mode not in ("live","demo"): raise ValueError("Choose the live or demo workspace.")
        if mode=="demo":
            owner=db.execute("SELECT * FROM users WHERE username=? AND role='Owner' AND active=1",(actor,)).fetchone()
            if not owner: raise PermissionError("An active owner account is required to start a demo workspace.")
            from .mockdata import prepare_demo_database
            prepare_demo_database(owner)
        database_module.set_demo_mode(mode=="demo")
        return {"mode":mode}
    if action=="clear_data":
        if role!="Owner": raise PermissionError("Only the owner can clear business data.")
        mode="demo" if database_module.DEMO_MODE else "live"
        if d.get("confirmation")!="CLEAR "+mode.upper()+" DATA": raise ValueError("Confirmation text does not match the active workspace.")
        backup_file=create_backup(db,prefix=mode)
        for table in ("loan_tx","cash","expenses","pending_returns","sale_items","sales","vendor_items","vendor_tx","vendor_payments","wages","advances","approvals","inventory","sessions","user_employee_links","employees","vendors","cylinders","audit"):
            db.execute("DELETE FROM "+table)
        audit(db,actor,"cleared","business_data",None,"Workspace "+mode+" cleared; backup "+backup_file.name)
        return {"mode":mode,"backup":backup_file.name}
    if action=="dashboard": return dashboard(db)
    if action=="list":
        table=d.get("table","")
        allowed={"employees":"employees","vendors":"vendors","cylinders":"cylinders","sessions":"sessions","sales":"sales","pending_returns":"pending_returns","inventory":"inventory","vendor_payments":"vendor_payments","expenses":"expenses","wages":"wages","advances":"advances","audit":"audit"}
        if table not in allowed: raise ValueError("Unknown list.")
        if role=="Employee":
            eid=user["employee_id"]
            if table in ("sessions","sales","pending_returns"): return rows(db,"SELECT * FROM "+allowed[table]+" WHERE employee_id=? ORDER BY rowid DESC LIMIT 500",(eid,))
            if table=="cylinders": return rows(db,"SELECT * FROM cylinders WHERE active=1 ORDER BY name")
        return rows(db,"SELECT * FROM "+allowed[table]+" ORDER BY rowid DESC LIMIT 500")
    if action=="report": return report(db,d,user)
    if action in ("export","export_pdf"):
        report_data=report(db,{"query":d.get("report"),"from_date":d.get("from_date",""),"to_date":d.get("to_date","")},user)
        if action=="export_pdf":
            label=re.sub(r"[^A-Za-z0-9_-]","_",str(d.get("report","report")))[:60] or "report"
            return {"pdf_data":make_pdf(label,report_data),"filename":label+".pdf"}
        return {"csv":csv_data(report_data),"filename":d.get("report","report")+".csv"}
    if action=="add_employee":
        name=_required_text(d.get("name"),"Employee name"); joined=_valid_date(d.get("joined",date.today().isoformat()),"joining")
        id=uid(); db.execute("INSERT INTO employees VALUES(?,?,?,?,?,?,?)",(id,name,d.get("contact",""),money(d.get("daily_wage",0)),joined,1,d.get("notes",""))); audit(db,actor,"created","employee",id); return {"id":id}
    if action=="add_vendor":
        name=_required_text(d.get("name"),"Vendor name")
        id=uid(); db.execute("INSERT INTO vendors VALUES(?,?,?,?,?)",(id,name,d.get("contact",""),d.get("notes",""),1)); audit(db,actor,"created","vendor",id); return {"id":id}
    if action=="add_cylinder":
        name=_required_text(d.get("name"),"Cylinder name"); category=d.get("category","Retail")
        if category not in ("Retail","Commercial"): raise ValueError("Choose Retail or Commercial for the cylinder category.")
        id=uid(); db.execute("INSERT INTO cylinders VALUES(?,?,?,?,?,?,?)",(id,name,d.get("capacity",""),category,money(d.get("sell_price",0)),money(d.get("buy_price",0)),1)); audit(db,actor,"created","cylinder",id); return {"id":id}
    if action=="stock_adjust":
        c=d.get("cylinder_id"); cond=d.get("condition"); loc=d.get("location"); direction=d.get("direction")
        if cond not in ("Full","Empty","Damaged"): raise ValueError("Choose a valid stock condition.")
        if loc not in ("Store","Employee","Vendor"): raise ValueError("Choose a valid stock location.")
        if direction not in ("in","out"): raise ValueError("Choose whether stock is added or removed.")
        quantity=qty(d.get("quantity"))
        if quantity<1: raise ValueError("Stock adjustment quantity must be at least one.")
        _required_text(d.get("reason"),"Adjustment reason")
        delta=quantity*(1 if direction=="in" else -1)
        threshold=int(scalar(db,"SELECT value FROM settings WHERE key='stock_adjustment_approval_threshold'") or 20)
        if abs(delta)>threshold and role!="Owner":
            aid=uid(); db.execute("INSERT INTO approvals VALUES(?,?,?,?,?,?,?,?,?)",(aid,actor,"stock_adjustment",json.dumps(d),"pending","","",now(),None)); audit(db,actor,"requested approval","stock_adjustment",aid,str(delta)); return {"approval_required":True,"approval_id":aid}
        movement(db,c,cond,loc,delta,"authorised adjustment: "+d.get("reason",""),actor); audit(db,actor,"stock adjustment","inventory",c,f"{delta} {cond} {loc}"); return {"stock":stock(db,c,cond,loc)}
    if action=="approvals":
        return rows(db,"SELECT id,requested_by,request_type,payload,status,decision_note,requested_at,decided_by,decided_at FROM approvals ORDER BY requested_at DESC LIMIT 500")
    if action=="approval_decision":
        if role!="Owner": raise PermissionError("Only the owner can approve or reject requests.")
        a=db.execute("SELECT * FROM approvals WHERE id=? AND status='pending'",(d["approval_id"],)).fetchone()
        if not a: raise ValueError("Approval request is no longer pending.")
        decision=d.get("decision")
        if decision not in ("approve","reject"): raise ValueError("Choose approve or reject.")
        if decision=="approve":
            payload=json.loads(a["payload"]); delta=qty(payload["quantity"])*(1 if payload.get("direction")=="in" else -1)
            movement(db,payload["cylinder_id"],payload["condition"],payload["location"],delta,"approved stock adjustment: "+payload.get("reason",""),a["requested_by"],a["id"])
        result_status="approved" if decision=="approve" else "rejected"
        db.execute("UPDATE approvals SET status=?,decided_by=?,decision_note=?,decided_at=? WHERE id=?",(result_status,actor,d.get("note",""),now(),a["id"]))
        audit(db,actor,result_status,"approval",a["id"],d.get("note","")); return {}
    if action=="update_settings":
        if role!="Owner": raise PermissionError("Only the owner can update approval settings.")
        threshold=qty(d.get("stock_adjustment_approval_threshold",20))
        db.execute("INSERT INTO settings VALUES('stock_adjustment_approval_threshold',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(threshold),))
        audit(db,actor,"updated","settings",None,"stock adjustment approval threshold "+str(threshold)); return {}
    if action=="get_settings":
        if role!="Owner": raise PermissionError("Only the owner can view these settings.")
        return {r["key"]:r["value"] for r in db.execute("SELECT key,value FROM settings")}
    if action=="open_session":
        eid=d.get("employee_id"); day=_valid_date(d.get("work_date",date.today().isoformat()),"work"); sid=uid(); items=d.get("items",[])
        if not db.execute("SELECT 1 FROM employees WHERE id=? AND active=1",(eid,)).fetchone(): raise ValueError("Choose an active employee.")
        if db.execute("SELECT 1 FROM sessions WHERE employee_id=? AND work_date=?",(eid,day)).fetchone():
            raise ValueError("A session already exists for this employee and date. If it is open, use it from the session dropdown. Closed sessions cannot be reopened.")
        if not items or not any(qty(it.get("quantity",0))>0 for it in items): raise ValueError("Add at least one cylinder issue line with a quantity greater than zero.")
        db.execute("INSERT INTO sessions(id,employee_id,work_date,vehicle,opened_at,status) VALUES(?,?,?,?,?,'open')",(sid,eid,day,d.get("vehicle",""),now()))
        opening={}
        for it in items:
            n=qty(it["quantity"])
            if n: movement(db,it["cylinder_id"],"Full","Store",-n,"session issue",actor,sid); movement(db,it["cylinder_id"],"Full","Employee",n,"session issue",actor,sid); opening[it["cylinder_id"]]=n
        db.execute("UPDATE sessions SET opening_full=? WHERE id=?",(json.dumps(opening),sid)); audit(db,actor,"opened","session",sid); return {"id":sid}
    if action=="sale":
        sid=d.get("session_id") or None; session=db.execute("SELECT * FROM sessions WHERE id=? AND status='open'",(sid,)).fetchone() if sid else None
        if sid and not session: raise ValueError("Choose an open employee session.")
        if role=="Employee" and (not session or session["employee_id"]!=user["employee_id"]): raise PermissionError("Employees can record sales only in their own open session.")
        eid=session["employee_id"] if session else d.get("employee_id") or None
        kind=d.get("kind");
        if kind not in ("exchange","new_connection","pending"): raise ValueError("Choose a valid sale type.")
        sale_id=uid(); amount=money(d.get("amount",0)); collected=money(d.get("collected",0)); items=d.get("items",[])
        sale_date=_valid_date(d.get("sale_date",date.today().isoformat()),"sale")
        if collected>amount: raise ValueError("Cash collected cannot exceed the sale amount.")
        if not items: raise ValueError("Add at least one cylinder line.")
        if kind=="pending" and d.get("due_date"):
            due=_valid_date(d["due_date"],"expected return")
            if due<sale_date: raise ValueError("Expected return date cannot be before the sale date.")
        db.execute("INSERT INTO sales VALUES(?,?,?,?,?,?,?,?,?,?,?)",(sale_id,sid,eid,sale_date,kind,amount,collected,d.get("expected_return",""),d.get("due_date",""),now(),actor))
        for it in items:
            c=it["cylinder_id"]; n=qty(it["quantity"]); price=money(it.get("unit_price",0)); empty=qty(it.get("empty_quantity",0))
            if n<1: raise ValueError("Sale quantity must be at least one.")
            if kind=="exchange" and empty>n: raise ValueError("Empty cylinders collected cannot exceed the quantity sold.")
            movement(db,c,"Full","Employee" if sid else "Store",-n,"sale",actor,sale_id)
            if kind=="exchange" and empty: movement(db,c,"Empty","Employee" if sid else "Store",empty,"sale exchange",actor,sale_id)
            db.execute("INSERT INTO sale_items VALUES(?,?,?,?,?,?)",(uid(),sale_id,c,n,price,empty))
            if kind=="pending" and n: db.execute("INSERT INTO pending_returns VALUES(?,?,?,?,?,?,?,?)",(uid(),sale_id,eid,c,n,0,d.get("due_date",""),"open"))
        if collected: db.execute("INSERT INTO cash VALUES(?,?,?,?,?,?,?,?,?)",(uid(),sid,eid,"collection",collected,"sale",f"Sale {sale_id[:8]}",actor,now()))
        audit(db,actor,"recorded","sale",sale_id,kind); return {"id":sale_id}
    if action=="return_pending":
        p=db.execute("SELECT * FROM pending_returns WHERE id=? AND status='open'",(d["return_id"],)).fetchone(); n=qty(d["quantity"])
        if not p or n<1 or n>p["quantity"]-p["returned"]: raise ValueError("Return quantity exceeds the outstanding balance.")
        if role=="Employee" and p["employee_id"]!=user["employee_id"]: raise PermissionError("Employees can settle only their own pending returns.")
        movement(db,p["cylinder_id"],"Empty","Store",n,"pending return",actor,p["id"])
        ret=p["returned"]+n; db.execute("UPDATE pending_returns SET returned=?,status=? WHERE id=?",(ret,"settled" if ret==p["quantity"] else "open",p["id"])); audit(db,actor,"settled pending return","pending_return",p["id"],str(n)); return {"returned":ret}
    if action=="cash":
        n=money(d["amount"]); kind=d["kind"]; sid=d.get("session_id") or None
        if n<=0: raise ValueError("Amount must be greater than zero.")
        if kind not in ("collection","expense"): raise ValueError("Choose a collection or expense entry.")
        session=db.execute("SELECT employee_id FROM sessions WHERE id=? AND status='open'",(sid,)).fetchone() if sid else None
        if sid and not session: raise ValueError("Choose an open session.")
        if role=="Employee" and (not session or session[0]!=user["employee_id"]): raise PermissionError("Employees can record cash only in their own open session.")
        eid=(session[0] if session else None) or d.get("employee_id") or None
        db.execute("INSERT INTO cash VALUES(?,?,?,?,?,?,?,?,?)",(uid(),sid,eid,kind,n,d.get("category",""),d.get("note",""),actor,now()))
        if kind=="expense": db.execute("INSERT INTO expenses VALUES(?,?,?,?,?,?,?,?,?,?)",(uid(),date.today().isoformat(),d.get("category","Other"),n,0,sid,eid,d.get("note",""),actor,now()))
        audit(db,actor,"recorded",kind,"",str(n)); return {}
    if action=="session_close_preview":
        if role not in ("Owner","Manager"): raise PermissionError("Only a manager or owner can prepare session closing counts.")
        session=db.execute("SELECT * FROM sessions WHERE id=? AND status='open'",(d.get("session_id"),)).fetchone()
        if not session: raise ValueError("Choose an open session.")
        issued=json.loads(session["opening_full"] or "{}")
        preview=[]
        for cylinder_id,quantity in issued.items():
            cylinder=db.execute("SELECT name FROM cylinders WHERE id=?",(cylinder_id,)).fetchone()
            sold=scalar(db,"SELECT COALESCE(SUM(si.quantity),0) FROM sales sa JOIN sale_items si ON si.sale_id=sa.id WHERE sa.session_id=? AND si.cylinder_id=?",(session["id"],cylinder_id))
            empties=scalar(db,"SELECT COALESCE(SUM(si.empty_quantity),0) FROM sales sa JOIN sale_items si ON si.sale_id=sa.id WHERE sa.session_id=? AND si.cylinder_id=?",(session["id"],cylinder_id))
            preview.append({"cylinder_id":cylinder_id,"cylinder":cylinder[0],"issued":int(quantity),"sold":int(sold),"full_to_return":max(0,int(quantity)-int(sold)),"empty_collected":int(empties)})
        return preview
    if action=="close_session":
        s=db.execute("SELECT * FROM sessions WHERE id=? AND status='open'",(d["session_id"],)).fetchone()
        if not s: raise ValueError("Session is not open.")
        full=json.loads(d.get("closing_full","{}")); empty=json.loads(d.get("closing_empty","{}")); damaged=json.loads(d.get("closing_damaged","{}"))
        issued=json.loads(s["opening_full"] or "{}")
        for cid,amount in issued.items():
            sold=scalar(db,"SELECT COALESCE(SUM(si.quantity),0) FROM sales sa JOIN sale_items si ON si.sale_id=sa.id WHERE sa.session_id=? AND si.cylinder_id=?",(s["id"],cid))
            expected=max(0,int(amount)-int(sold))
            actual=qty(full.get(cid,0))
            if actual!=expected:
                cylinder_name=scalar(db,"SELECT name FROM cylinders WHERE id=?",(cid,))
                raise ValueError(f"{cylinder_name}: enter {expected} full cylinders returned (issued less recorded sales); entered {actual}.")
        for c in db.execute("SELECT id FROM cylinders").fetchall():
            cid=c[0]
            for cond,box in (("Full",full),("Empty",empty),("Damaged",damaged)):
                n=qty(box.get(cid,0))
                if n:
                    if cond=="Full":
                        movement(db,cid,cond,"Employee",-n,"session close return",actor,s["id"])
                        movement(db,cid,cond,"Store",n,"session close return",actor,s["id"])
                    elif cond=="Empty":
                        movement(db,cid,cond,"Employee",-n,"session close return",actor,s["id"])
                        movement(db,cid,cond,"Store",n,"session close return",actor,s["id"])
                    else:
                        movement(db,cid,cond,"Store",n,"session close return",actor,s["id"])
        collections=scalar(db,"SELECT COALESCE(SUM(amount),0) FROM cash WHERE session_id=? AND kind='collection'",(s["id"],))
        exp=scalar(db,"SELECT COALESCE(SUM(amount),0) FROM cash WHERE session_id=? AND kind='expense'",(s["id"],))
        expected=round(collections-exp,2); actual=money(d.get("actual_cash",0)); discrepancy=d.get("discrepancy","")
        if round(actual-expected,2)!=0 and not discrepancy.strip(): raise ValueError("Explain the cash shortage or excess before closing.")
        db.execute("UPDATE sessions SET closed_at=?,closing_full=?,closing_empty=?,closing_damaged=?,expected_cash=?,actual_cash=?,discrepancy=?,verified_by=?,status='closed' WHERE id=?",(now(),json.dumps(full),json.dumps(empty),json.dumps(damaged),expected,actual,discrepancy,d.get("verified_by",actor),s["id"]))
        emp=db.execute("SELECT daily_wage FROM employees WHERE id=?",(s["employee_id"],)).fetchone(); db.execute("INSERT INTO wages VALUES(?,?,?,?,?,?,?,?,?,?)",(uid(),s["employee_id"],s["id"],s["work_date"],emp[0],0,"","",actor,now()))
        audit(db,actor,"closed","session",s["id"],f"expected {expected}, actual {actual}"); return {"expected_cash":expected,"difference":round(actual-expected,2)}
    if action=="vendor_delivery":
        vid=d["vendor_id"]; txid=uid(); total=0; items=d.get("items",[])
        if not items: raise ValueError("Add at least one vendor delivery line.")
        for it in items:
            if it.get("kind") not in ("received","empty_sent","damaged_sent"): raise ValueError("Choose a valid vendor movement type.")
            if qty(it.get("quantity",0))<1: raise ValueError("Vendor delivery quantity must be at least one.")
            if it["kind"]=="received": total+=money(it.get("unit_price",0))*qty(it.get("quantity",0))
        db.execute("INSERT INTO vendor_tx VALUES(?,?,?,?,?,?,?)",(txid,vid,d.get("tx_date",date.today().isoformat()),d.get("note",""),total,actor,now()))
        for it in items:
            c=it["cylinder_id"]; n=qty(it["quantity"]); price=money(it.get("unit_price",0)); kind=it["kind"]
            if n:
                if kind=="received": movement(db,c,"Full","Store",n,"vendor received",actor,txid)
                elif kind=="empty_sent": movement(db,c,"Empty","Store",-n,"sent to vendor",actor,txid)
                elif kind=="damaged_sent": movement(db,c,"Damaged","Store",-n,"damaged sent to vendor",actor,txid)
                db.execute("INSERT INTO vendor_items VALUES(?,?,?,?,?,?)",(uid(),txid,c,kind,n,price))
        audit(db,actor,"recorded","vendor_transaction",txid); return {"id":txid,"amount":total}
    if action=="vendor_payment":
        n=money(d["amount"]);
        if n<=0: raise ValueError("Payment amount must be greater than zero.")
        day=_valid_date(d.get("payment_date",date.today().isoformat()),"payment")
        db.execute("INSERT INTO vendor_payments VALUES(?,?,?,?,?,?,?,?,?)",(uid(),d["vendor_id"],n,day,d.get("method","Cash"),d.get("reference",""),d.get("note",""),actor,now())); audit(db,actor,"recorded","vendor_payment","",str(n)); return {}
    if action=="business_expense":
        n=money(d["amount"]);
        if n<=0: raise ValueError("Expense amount must be greater than zero.")
        day=_valid_date(d.get("expense_date",date.today().isoformat()),"expense")
        category=_required_text(d.get("category","Other"),"Expense category")
        db.execute("INSERT INTO expenses VALUES(?,?,?,?,?,NULL,NULL,?,?,?)",(uid(),day,category,n,1,d.get("note",""),actor,now())); audit(db,actor,"recorded","business_expense","",str(n)); return {}
    if action=="bulk_expenses":
        items=d.get("rows",[])
        if not items or len(items)>500: raise ValueError("Import between 1 and 500 expense rows at a time.")
        cleaned=[]
        for i,x in enumerate(items,1):
            try: day=date.fromisoformat(x.get("expense_date","")).isoformat()
            except ValueError: raise ValueError(f"Row {i}: use YYYY-MM-DD for the expense date.")
            category=x.get("category","").strip()
            if not category: raise ValueError(f"Row {i}: category is required.")
            cleaned.append((day,category,money(x.get("amount")),x.get("note","").strip()))
        for day,category,amount,note in cleaned:
            db.execute("INSERT INTO expenses VALUES(?,?,?,?,?,NULL,NULL,?,?,?)",(uid(),day,category,amount,1,note,actor,now()))
        audit(db,actor,"bulk imported","business_expenses","",f"{len(cleaned)} rows")
        return {"imported":len(cleaned)}
    if action=="pay_wage":
        w=db.execute("SELECT * FROM wages WHERE id=?",(d["wage_id"],)).fetchone(); n=money(d.get("paid",0))
        if not w or n>w["amount"]-w["paid"]: raise ValueError("Payment exceeds the unpaid wage balance.")
        db.execute("UPDATE wages SET paid=paid+?,paid_on=? WHERE id=?",(n,date.today().isoformat(),w["id"])); audit(db,actor,"paid wage", "wage",w["id"],str(n)); return {}
    if action=="advance":
        n=money(d["amount"]); db.execute("INSERT INTO advances VALUES(?,?,?,?,?,?,?)",(uid(),d["employee_id"],d.get("advance_date",date.today().isoformat()),n,d.get("reason",""),actor,now())); audit(db,actor,"recorded","advance","",str(n)); return {}
    if action=="repay_advance":
        a=db.execute("SELECT * FROM advances WHERE id=?",(d["advance_id"],)).fetchone(); paid=scalar(db,"SELECT COALESCE(SUM(amount),0) FROM loan_tx WHERE advance_id=?",(d["advance_id"],)); n=money(d["amount"])
        if not a or n>a["amount"]-paid: raise ValueError("Repayment exceeds the outstanding advance.")
        if d.get("method")=="Salary deduction":
            unpaid=rows(db,"SELECT id,amount,paid FROM wages WHERE employee_id=? AND amount>paid ORDER BY work_date",(a["employee_id"],))
            if sum(x["amount"]-x["paid"] for x in unpaid)<n: raise ValueError("There is not enough unpaid wage balance for this deduction.")
            remaining=n
            for w in unpaid:
                take=min(remaining,w["amount"]-w["paid"])
                if take: db.execute("UPDATE wages SET paid=paid+?,paid_on=? WHERE id=?",(take,date.today().isoformat(),w["id"])); remaining=round(remaining-take,2)
                if not remaining: break
        db.execute("INSERT INTO loan_tx VALUES(?,?,?,?,?,?,?,?)",(uid(),a["id"],date.today().isoformat(),n,d.get("method","Cash"),d.get("note",""),actor,now())); audit(db,actor,"repaid","advance",a["id"],str(n)); return {}
    if action=="users":
        if role!="Owner": raise PermissionError("Only the owner can manage users.")
        return rows(db,"SELECT u.id,u.username,u.role,e.name employee,u.active,u.created_at FROM users u LEFT JOIN user_employee_links l ON l.user_id=u.id LEFT JOIN employees e ON e.id=l.employee_id ORDER BY u.username")
    if action=="add_user":
        if role!="Owner": raise PermissionError("Only the owner can add users.")
        username=d["username"].strip(); pw=d["password"]
        if len(pw)<10: raise ValueError("Use a password with at least 10 characters.")
        new_role=d.get("role","Manager"); p,s=password_hash(pw); id=uid(); db.execute("INSERT INTO users VALUES(?,?,?,?,?,?,?)",(id,username,p,s,new_role,1,now()))
        if new_role=="Employee":
            eid=d.get("employee_id")
            if not eid or not db.execute("SELECT 1 FROM employees WHERE id=? AND active=1",(eid,)).fetchone(): raise ValueError("Link the Employee account to an active employee record.")
            db.execute("INSERT INTO user_employee_links VALUES(?,?)",(id,eid))
        audit(db,actor,"created","user",id,username); return {}
    if action=="backup":
        target=create_backup(db,prefix="demo" if database_module.DEMO_MODE else "store")
        return {"file":str(target)}
    if action=="backups":
        if role!="Owner": raise PermissionError("Only the owner can view restore points.")
        prefix="demo" if database_module.DEMO_MODE else "store"
        return [{"name":p.name,"modified":datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="minutes")} for p in sorted(BACKUPS.glob(prefix+"-*.db"),key=lambda p:p.stat().st_mtime,reverse=True)]
    if action=="restore_backup":
        if role!="Owner": raise PermissionError("Only the owner can restore a backup.")
        name=Path(d.get("name","")).name
        prefix="demo" if database_module.DEMO_MODE else "store"
        if name!=d.get("name") or not name.startswith(prefix+"-") or not name.endswith(".db"): raise ValueError("Choose a valid backup file for the active workspace.")
        source_path=(BACKUPS/name).resolve()
        if source_path.parent!=BACKUPS.resolve() or not source_path.is_file(): raise ValueError("Backup file was not found.")
        source=sqlite3.connect(source_path)
        try:
            if source.execute("PRAGMA integrity_check").fetchone()[0]!="ok": raise ValueError("Backup database integrity check failed.")
            source.backup(db)
        finally: source.close()
        db.executescript(SCHEMA)
        db.execute("INSERT OR IGNORE INTO settings VALUES('stock_adjustment_approval_threshold','20')")
        audit(db,actor,"restored","backup",name)
        return {"restored":name}
    if action=="change_password":
        pw=d["password"]
        if len(pw)<10: raise ValueError("Use a password with at least 10 characters.")
        p,s=password_hash(pw); db.execute("UPDATE users SET password=?,salt=? WHERE username=?",(p,s,actor)); audit(db,actor,"changed","password"); return {}
    raise ValueError("Unknown action.")


class StoreService:
    """Application boundary: owns the transaction around one use case."""

    def __init__(self, connection_factory, transaction_lock):
        self._connection_factory = connection_factory
        self._transaction_lock = transaction_lock

    def execute(self, action, payload, user):
        with self._transaction_lock, self._connection_factory() as connection:
            return _dispatch(connection, action, payload, user)

