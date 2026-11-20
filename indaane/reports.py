from .database import rows, scalar
from datetime import date
def dashboard(db):
    st=rows(db,"SELECT c.id,c.name,c.category, i.condition,i.location,COALESCE(SUM(i.quantity),0) quantity FROM cylinders c LEFT JOIN inventory i ON i.cylinder_id=c.id GROUP BY c.id,i.condition,i.location ORDER BY c.name")
    today=date.today().isoformat()
    return {"stock":st,"sales_today":scalar(db,"SELECT COALESCE(SUM(amount),0) FROM sales WHERE sale_date=?",(today,)),"collections_today":scalar(db,"SELECT COALESCE(SUM(amount),0) FROM cash WHERE kind='collection' AND date(created_at)=?",(today,)),"expenses_today":scalar(db,"SELECT COALESCE(SUM(amount),0) FROM expenses WHERE expense_date=?",(today,)),"open_sessions":scalar(db,"SELECT COUNT(*) FROM sessions WHERE status='open'"),"pending_returns":scalar(db,"SELECT COALESCE(SUM(quantity-returned),0) FROM pending_returns WHERE status='open'"),"vendor_balance":scalar(db,"SELECT (SELECT COALESCE(SUM(amount),0) FROM vendor_tx)-(SELECT COALESCE(SUM(amount),0) FROM vendor_payments)")}

def report(db,d,user):
    q=d.get("query","")
    role=user["role"]
    start=d.get("from_date",""); end=d.get("to_date","")
    if q=="sales":
        where=[]; args=[]
        if start: where.append("s.sale_date>=?"); args.append(start)
        if end: where.append("s.sale_date<=?"); args.append(end)
        clause=(" WHERE "+" AND ".join(where)) if where else ""
        return rows(db,"SELECT s.sale_date,s.kind,e.name employee,s.amount,s.collected,c.name cylinder,si.quantity,si.unit_price FROM sales s LEFT JOIN employees e ON e.id=s.employee_id JOIN sale_items si ON si.sale_id=s.id JOIN cylinders c ON c.id=si.cylinder_id"+clause+" ORDER BY s.sale_date DESC LIMIT 2000",args)
    if q=="employee_performance":
        where=[]; args=[]
        if start: where.append("work_date>=?"); args.append(start)
        if end: where.append("work_date<=?"); args.append(end)
        clause=(" AND "+" AND ".join(where)) if where else ""
        return rows(db,"SELECT e.name employee,COUNT(DISTINCT s.id) sessions,COALESCE((SELECT SUM(sa.amount) FROM sales sa WHERE sa.employee_id=e.id AND (?='' OR sa.sale_date>=?) AND (?='' OR sa.sale_date<=?)),0) sales,COALESCE((SELECT SUM(c.amount) FROM cash c WHERE c.employee_id=e.id AND c.kind='collection' AND (?='' OR date(c.created_at)>=?) AND (?='' OR date(c.created_at)<=?)),0) collections,COALESCE((SELECT SUM(ABS(s2.actual_cash-s2.expected_cash)) FROM sessions s2 WHERE s2.employee_id=e.id AND s2.status='closed' AND (?='' OR s2.work_date>=?) AND (?='' OR s2.work_date<=?)),0) cash_difference FROM employees e LEFT JOIN sessions s ON s.employee_id=e.id AND (?='' OR s.work_date>=?) AND (?='' OR s.work_date<=?) GROUP BY e.id ORDER BY sales DESC",(start,start,end,end,start,start,end,end,start,start,end,end,start,start,end,end))
    if q=="discrepancies":
        return rows(db,"SELECT work_date,e.name employee,expected_cash,actual_cash,ROUND(actual_cash-expected_cash,2) difference,discrepancy,verified_by FROM sessions s JOIN employees e ON e.id=s.employee_id WHERE status='closed' AND ABS(actual_cash-expected_cash)>0.005 AND (?='' OR work_date>=?) AND (?='' OR work_date<=?) ORDER BY work_date DESC",(start,start,end,end))
    if q=="audit":
        return rows(db,"SELECT created_at,actor,action,entity,entity_id,details FROM audit WHERE (?='' OR date(created_at)>=?) AND (?='' OR date(created_at)<=?) ORDER BY created_at DESC LIMIT 2000",(start,start,end,end))
    if q=="sales_trend":
        return rows(db,"WITH RECURSIVE days(d) AS (SELECT date('now','-13 days') UNION ALL SELECT date(d,'+1 day') FROM days WHERE d<date('now')) SELECT days.d date,COALESCE(SUM(s.amount),0) sales,COUNT(s.id) transactions FROM days LEFT JOIN sales s ON s.sale_date=days.d GROUP BY days.d ORDER BY days.d")
    if q=="inventory_adjustments":
        return rows(db,"SELECT i.created_at,c.name cylinder,i.condition,i.location,i.quantity,i.source,i.actor FROM inventory i JOIN cylinders c ON c.id=i.cylinder_id WHERE i.source LIKE '%adjustment%' AND (?='' OR date(i.created_at)>=?) AND (?='' OR date(i.created_at)<=?) ORDER BY i.created_at DESC",(start,start,end,end))
    if q=="closing_statement":
        sid=d.get("session_id","")
        s=db.execute("SELECT s.*,e.name employee,e.daily_wage FROM sessions s JOIN employees e ON e.id=s.employee_id WHERE s.id=? AND s.status='closed'",(sid,)).fetchone()
        if not s: raise ValueError("Choose a closed employee session.")
        sales=rows(db,"SELECT sa.sale_date,sa.kind,sa.amount,sa.collected,c.name cylinder,si.quantity,si.unit_price,si.empty_quantity FROM sales sa JOIN sale_items si ON si.sale_id=sa.id JOIN cylinders c ON c.id=si.cylinder_id WHERE sa.session_id=? ORDER BY sa.created_at",(sid,))
        expenses=rows(db,"SELECT category,amount,note FROM expenses WHERE session_id=? ORDER BY created_at",(sid,))
        return {"session":dict(s),"sales":sales,"expenses":expenses}
    if q=="inventory": return rows(db,"SELECT c.name,c.category,i.condition,i.location,SUM(i.quantity) quantity FROM inventory i JOIN cylinders c ON c.id=i.cylinder_id GROUP BY c.id,i.condition,i.location ORDER BY c.name")
    if q=="sales": return rows(db,"SELECT s.sale_date,s.kind,e.name employee,s.amount,s.collected,c.name cylinder,si.quantity,si.unit_price FROM sales s LEFT JOIN employees e ON e.id=s.employee_id JOIN sale_items si ON si.sale_id=s.id JOIN cylinders c ON c.id=si.cylinder_id ORDER BY s.sale_date DESC LIMIT 1000")
    if q=="vendors": return rows(db,"SELECT v.name vendor,COALESCE((SELECT SUM(amount) FROM vendor_tx WHERE vendor_id=v.id),0) purchases,COALESCE((SELECT SUM(amount) FROM vendor_payments WHERE vendor_id=v.id),0) paid FROM vendors v")
    if q=="pending":
        if role=="Employee": return rows(db,"SELECT p.*,e.name employee,c.name cylinder FROM pending_returns p LEFT JOIN employees e ON e.id=p.employee_id JOIN cylinders c ON c.id=p.cylinder_id WHERE p.status='open' AND p.employee_id=?",(user["employee_id"],))
        return rows(db,"SELECT p.*,e.name employee,c.name cylinder FROM pending_returns p LEFT JOIN employees e ON e.id=p.employee_id JOIN cylinders c ON c.id=p.cylinder_id WHERE status='open'")
    if q=="cash": return rows(db,"SELECT s.work_date,e.name employee,s.expected_cash,s.actual_cash,s.actual_cash-s.expected_cash difference,s.discrepancy,s.status FROM sessions s JOIN employees e ON e.id=s.employee_id ORDER BY s.work_date DESC")
    if q=="finance": return rows(db,"SELECT expense_date date,'Expense' type,category description,amount FROM expenses UNION ALL SELECT work_date,'Wage',e.name,w.amount FROM wages w JOIN employees e ON e.id=w.employee_id ORDER BY date DESC")
    if q=="employees": return rows(db,"SELECT e.name employee,(SELECT COUNT(*) FROM sessions s WHERE s.employee_id=e.id) sessions,(SELECT COALESCE(SUM(amount),0) FROM sales sa WHERE sa.employee_id=e.id) sales,(SELECT COALESCE(SUM(amount),0) FROM wages w WHERE w.employee_id=e.id) wages FROM employees e")
    if q=="advances": return rows(db,"SELECT e.name employee,a.advance_date,a.amount advanced,COALESCE((SELECT SUM(amount) FROM loan_tx WHERE advance_id=a.id),0) repaid,a.amount-COALESCE((SELECT SUM(amount) FROM loan_tx WHERE advance_id=a.id),0) outstanding FROM advances a JOIN employees e ON e.id=a.employee_id")
    if q=="expenses": return rows(db,"SELECT * FROM expenses ORDER BY expense_date DESC")
    raise ValueError("Unknown report.")
