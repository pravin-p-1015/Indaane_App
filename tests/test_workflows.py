"""Integration coverage for the local store application service."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from indaane import backups, database, security, services


class StoreApplicationTests(unittest.TestCase):
    def setUp(self):
        test_root = Path(__file__).resolve().parents[1] / ".test-tmp"
        test_root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=test_root)
        root = Path(self.temp.name)
        self.db_path = root / "store.db"
        self.backup_path = root / "backups"
        self.backup_path.mkdir()
        self._patches = [
            patch.object(database, "DB", self.db_path),
            patch.object(database, "DEMO_DB", root / "demo.db"),
            patch.object(database, "BACKUPS", self.backup_path),
            patch.object(backups, "BACKUPS", self.backup_path),
            patch.object(services, "BACKUPS", self.backup_path),
        ]
        for item in self._patches:
            item.start()
        database.set_demo_mode(False)
        security.SESSIONS.clear()
        database.init_db()
        self.app = services.StoreService(database.connect, database.LOCK)
        self.owner = {"id": "test-owner", "username": "admin", "role": "Owner", "employee_id": None}

    def tearDown(self):
        database.set_demo_mode(False)
        security.SESSIONS.clear()
        for item in reversed(self._patches):
            item.stop()
        self.temp.cleanup()

    def call(self, action, payload=None, user=None):
        return self.app.execute(action, payload or {}, user or self.owner)

    def cylinder(self, name="Retail 14 kg", **overrides):
        values = {"name": name, "capacity": "14 kg", "category": "Retail", "sell_price": 100, "buy_price": 50}
        values.update(overrides)
        return self.call("add_cylinder", values)["id"]

    def employee(self, name="Ravi", wage=750):
        return self.call("add_employee", {"name": name, "daily_wage": wage, "joined": "2026-01-01"})["id"]

    def stock_in(self, cylinder_id, quantity, condition="Full"):
        self.call("stock_adjust", {"cylinder_id": cylinder_id, "condition": condition, "location": "Store", "direction": "in", "quantity": quantity, "reason": "Opening stock"})

    def stock_at(self, cylinder_id, condition, location):
        with database.connect() as db:
            return database.stock(db, cylinder_id, condition, location)

    def test_master_data_inventory_and_negative_stock_guard(self):
        cylinder_id = self.cylinder()
        self.stock_in(cylinder_id, 8)
        self.assertEqual(self.stock_at(cylinder_id, "Full", "Store"), 8)
        with self.assertRaisesRegex(ValueError, "Insufficient full stock"):
            self.call("stock_adjust", {"cylinder_id": cylinder_id, "condition": "Full", "location": "Store", "direction": "out", "quantity": 9, "reason": "Count correction"})
        self.call("add_vendor", {"name": "North Supply", "contact": ""})
        types = self.call("list", {"table": "cylinders"})
        self.assertEqual(types[0]["id"], cylinder_id)
        self.assertEqual(self.call("dashboard")["stock"], [{"id": cylinder_id, "name": "Retail 14 kg", "category": "Retail", "condition": "Full", "location": "Store", "quantity": 8}])

    def test_employee_session_exchange_cash_reconciliation_and_wage(self):
        cylinder_id = self.cylinder()
        self.stock_in(cylinder_id, 7)
        employee_id = self.employee()
        session_id = self.call("open_session", {"employee_id": employee_id, "work_date": "2026-11-19", "items": [{"cylinder_id": cylinder_id, "quantity": 3}]})["id"]
        sale = self.call("sale", {"session_id": session_id, "kind": "exchange", "sale_date": "2026-11-19", "amount": 200, "collected": 200, "items": [{"cylinder_id": cylinder_id, "quantity": 2, "unit_price": 100, "empty_quantity": 1}]})
        self.assertTrue(sale["id"])
        preview = self.call("session_close_preview", {"session_id": session_id})
        self.assertEqual(preview, [{"cylinder_id": cylinder_id, "cylinder": "Retail 14 kg", "issued": 3, "sold": 2, "full_to_return": 1, "empty_collected": 1}])
        self.call("cash", {"session_id": session_id, "kind": "expense", "amount": 10, "category": "Petrol", "note": "Route fuel"})
        closed = self.call("close_session", {"session_id": session_id, "closing_full": json.dumps({cylinder_id: 1}), "closing_empty": json.dumps({cylinder_id: 1}), "closing_damaged": "{}", "actual_cash": 190, "verified_by": "Owner"})
        self.assertEqual(closed, {"expected_cash": 190.0, "difference": 0.0})
        self.assertEqual(self.stock_at(cylinder_id, "Full", "Store"), 5)
        wages = self.call("list", {"table": "wages"})
        self.assertEqual(wages[0]["amount"], 750)
        self.call("pay_wage", {"wage_id": wages[0]["id"], "paid": 250})
        self.assertEqual(self.call("list", {"table": "wages"})[0]["paid"], 250)
        cash_report = self.call("report", {"query": "cash"})
        self.assertEqual(cash_report[0]["difference"], 0.0)

    def test_session_validation_messages_are_actionable(self):
        cylinder_id = self.cylinder()
        self.stock_in(cylinder_id, 2)
        employee_id = self.employee()
        with self.assertRaisesRegex(ValueError, "at least one cylinder issue line"):
            self.call("open_session", {"employee_id": employee_id, "work_date": "2026-11-19", "items": []})
        session_id = self.call("open_session", {"employee_id": employee_id, "work_date": "2026-11-19", "items": [{"cylinder_id": cylinder_id, "quantity": 2}]})["id"]
        with self.assertRaisesRegex(ValueError, "already exists for this employee and date"):
            self.call("open_session", {"employee_id": employee_id, "work_date": "2026-11-19", "items": [{"cylinder_id": cylinder_id, "quantity": 1}]})
        with self.assertRaisesRegex(ValueError, "enter 2 full cylinders returned"):
            self.call("close_session", {"session_id": session_id, "closing_full": "{}", "closing_empty": "{}", "closing_damaged": "{}", "actual_cash": 0})
        with self.assertRaisesRegex(ValueError, "Explain the cash shortage or excess"):
            self.call("close_session", {"session_id": session_id, "closing_full": json.dumps({cylinder_id: 2}), "closing_empty": "{}", "closing_damaged": "{}", "actual_cash": 1})

    def test_invalid_inputs_are_rejected_without_partial_records(self):
        cylinder_id = self.cylinder()
        self.stock_in(cylinder_id, 4)
        with self.assertRaisesRegex(ValueError, "Employee name is required"):
            self.call("add_employee", {"name": "   "})
        with self.assertRaisesRegex(ValueError, "Vendor name is required"):
            self.call("add_vendor", {"name": ""})
        with self.assertRaisesRegex(ValueError, "valid stock condition"):
            self.call("stock_adjust", {"cylinder_id": cylinder_id, "condition": "Broken-ish", "location": "Store", "direction": "in", "quantity": 1, "reason": "Count"})
        with self.assertRaisesRegex(ValueError, "whole-number quantity"):
            self.call("stock_adjust", {"cylinder_id": cylinder_id, "condition": "Full", "location": "Store", "direction": "in", "quantity": "1.5", "reason": "Count"})
        with self.assertRaisesRegex(ValueError, "at least one cylinder issue line with a quantity greater than zero"):
            self.call("open_session", {"employee_id": self.employee(), "work_date": "2026-11-19", "items": [{"cylinder_id": cylinder_id, "quantity": 0}]})
        with self.assertRaisesRegex(ValueError, "valid sale type"):
            self.call("sale", {"kind": "refund", "amount": 10, "collected": 0, "items": [{"cylinder_id": cylinder_id, "quantity": 1, "unit_price": 10}]})
        with self.assertRaisesRegex(ValueError, "cannot exceed the sale amount"):
            self.call("sale", {"kind": "exchange", "amount": 10, "collected": 11, "items": [{"cylinder_id": cylinder_id, "quantity": 1, "unit_price": 10}]})
        with self.assertRaisesRegex(ValueError, "valid sale date"):
            self.call("sale", {"kind": "new_connection", "sale_date": "not-a-date", "amount": 10, "collected": 10, "items": [{"cylinder_id": cylinder_id, "quantity": 1, "unit_price": 10}]})
        self.assertEqual(self.call("list", {"table": "sales"}), [])
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            self.call("cash", {"kind": "collection", "amount": 0})
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            self.call("cash", {"kind": "collection", "amount": -1})
        self.assertEqual(self.call("report", {"query": "cash"}), [])

    def test_pending_empty_return_can_be_partially_settled(self):
        cylinder_id = self.cylinder()
        self.stock_in(cylinder_id, 4)
        employee_id = self.employee()
        self.call("sale", {"employee_id": employee_id, "kind": "pending", "sale_date": "2026-11-19", "amount": 200, "collected": 100, "due_date": "2026-11-22", "items": [{"cylinder_id": cylinder_id, "quantity": 2, "unit_price": 100, "empty_quantity": 0}]})
        pending = self.call("report", {"query": "pending"})
        self.assertEqual(pending[0]["quantity"] - pending[0]["returned"], 2)
        self.call("return_pending", {"return_id": pending[0]["id"], "quantity": 1})
        pending = self.call("report", {"query": "pending"})
        self.assertEqual(pending[0]["quantity"] - pending[0]["returned"], 1)
        self.call("return_pending", {"return_id": pending[0]["id"], "quantity": 1})
        self.assertEqual(self.call("report", {"query": "pending"}), [])
        self.assertEqual(self.stock_at(cylinder_id, "Empty", "Store"), 2)

    def test_vendor_purchase_payment_expense_advances_and_wage_payment(self):
        cylinder_id = self.cylinder()
        vendor_id = self.call("add_vendor", {"name": "North Supply"})["id"]
        self.call("vendor_delivery", {"vendor_id": vendor_id, "tx_date": "2026-11-19", "items": [{"cylinder_id": cylinder_id, "kind": "received", "quantity": 5, "unit_price": 50}]})
        balance = self.call("report", {"query": "vendors"})[0]
        self.assertEqual(balance["purchases"], 250)
        self.call("vendor_payment", {"vendor_id": vendor_id, "amount": 100, "payment_date": "2026-11-19", "method": "UPI"})
        self.assertEqual(self.call("report", {"query": "vendors"})[0]["paid"], 100)
        self.call("business_expense", {"expense_date": "2026-11-19", "category": "Electricity", "amount": 30, "note": "Bill"})
        employee_id = self.employee()
        self.call("advance", {"employee_id": employee_id, "amount": 200, "reason": "Travel"})
        advance_id = self.call("list", {"table": "advances"})[0]["id"]
        self.call("repay_advance", {"advance_id": advance_id, "amount": 50, "method": "Cash"})
        advance_report = self.call("report", {"query": "advances"})[0]
        self.assertEqual(advance_report["outstanding"], 150)
        expenses = self.call("report", {"query": "expenses"})
        self.assertEqual(len(expenses), 1)

    def test_employee_login_is_linked_and_scoped_to_own_session(self):
        cylinder_id = self.cylinder()
        self.stock_in(cylinder_id, 4)
        own_employee = self.employee("Employee One")
        other_employee = self.employee("Employee Two")
        own_session = self.call("open_session", {"employee_id": own_employee, "work_date": "2026-11-19", "items": [{"cylinder_id": cylinder_id, "quantity": 1}]})["id"]
        other_session = self.call("open_session", {"employee_id": other_employee, "work_date": "2026-11-19", "items": [{"cylinder_id": cylinder_id, "quantity": 1}]})["id"]
        self.call("add_user", {"username": "worker1", "password": "secure-password", "role": "Employee", "employee_id": own_employee})
        auth = security.AuthenticationService(database.connect, database.LOCK, database.audit)
        token = auth.login("worker1", "secure-password")
        worker = auth.session(token)
        self.assertEqual(worker["employee_id"], own_employee)
        self.assertEqual([x["id"] for x in self.call("list", {"table": "sessions"}, worker)], [own_session])
        with self.assertRaises(PermissionError):
            self.call("sale", {"session_id": other_session, "kind": "exchange", "amount": 100, "collected": 100, "items": [{"cylinder_id": cylinder_id, "quantity": 1, "unit_price": 100}]}, worker)
        auth.logout(token)
        self.assertIsNone(auth.session(token))

    def test_owner_approval_flow_for_large_stock_adjustment(self):
        cylinder_id = self.cylinder()
        self.call("add_user", {"username": "manager", "password": "secure-password", "role": "Manager"})
        manager = {"id": "test-manager", "username": "manager", "role": "Manager", "employee_id": None}
        self.call("update_settings", {"stock_adjustment_approval_threshold": 2})
        self.assertEqual(self.call("get_settings")["stock_adjustment_approval_threshold"], "2")
        submitted = self.call("stock_adjust", {"cylinder_id": cylinder_id, "condition": "Full", "location": "Store", "direction": "in", "quantity": 25, "reason": "Delivery count"}, manager)
        self.assertTrue(submitted["approval_required"])
        self.assertEqual(self.stock_at(cylinder_id, "Full", "Store"), 0)
        self.call("approval_decision", {"approval_id": submitted["approval_id"], "decision": "approve"})
        self.assertEqual(self.stock_at(cylinder_id, "Full", "Store"), 25)
        rejected = self.call("stock_adjust", {"cylinder_id": cylinder_id, "condition": "Full", "location": "Store", "direction": "in", "quantity": 3, "reason": "Duplicate count"}, manager)
        self.call("approval_decision", {"approval_id": rejected["approval_id"], "decision": "reject", "note": "Count already posted"})
        status = next(a["status"] for a in self.call("approvals") if a["id"] == rejected["approval_id"])
        self.assertEqual(status, "rejected")

    def test_date_filtered_reports_csv_and_pdf_export(self):
        cylinder_id = self.cylinder()
        self.stock_in(cylinder_id, 3)
        self.call("sale", {"kind": "new_connection", "sale_date": "2026-11-19", "amount": 100, "collected": 50, "items": [{"cylinder_id": cylinder_id, "quantity": 1, "unit_price": 100}]})
        report = self.call("report", {"query": "sales", "from_date": "2026-11-19", "to_date": "2026-11-19"})
        self.assertEqual(len(report), 1)
        csv_export = self.call("export", {"report": "sales", "from_date": "2026-11-19", "to_date": "2026-11-19"})
        self.assertIn("sale_date", csv_export["csv"])
        pdf_export = self.call("export_pdf", {"report": "sales", "from_date": "2026-11-19", "to_date": "2026-11-19"})
        self.assertTrue(pdf_export["pdf_data"].startswith(b"%PDF-1.4"))
        self.assertIn(b"Indaane Cylinder Store", pdf_export["pdf_data"])

    def test_bulk_expense_import_is_validated_and_atomic(self):
        result = self.call("bulk_expenses", {"rows": [{"expense_date": "2026-11-19", "category": "Rent", "amount": "100", "note": "A"}, {"expense_date": "2026-11-19", "category": "Power", "amount": "25", "note": "B"}]})
        self.assertEqual(result["imported"], 2)
        with self.assertRaisesRegex(ValueError, "Row 2: use YYYY-MM-DD"):
            self.call("bulk_expenses", {"rows": [{"expense_date": "2026-11-19", "category": "Rent", "amount": "10"}, {"expense_date": "bad-date", "category": "Power", "amount": "5"}]})
        self.assertEqual(len(self.call("report", {"query": "expenses"})), 2)

    def test_backup_restore_recovers_database_snapshot(self):
        self.employee("Before backup")
        backup_file = self.call("backup")["file"]
        self.employee("After backup")
        self.assertEqual(len(self.call("list", {"table": "employees"})), 2)
        self.call("restore_backup", {"name": Path(backup_file).name})
        employees = self.call("list", {"table": "employees"})
        self.assertEqual([e["name"] for e in employees], ["Before backup"])

    def test_demo_workspace_is_isolated_and_clear_creates_backup(self):
        live_cylinder=self.cylinder("Live only")
        self.assertEqual(self.call("data_status"),{"mode":"live"})
        self.call("data_mode",{"mode":"demo"})
        self.assertEqual(self.call("data_status"),{"mode":"demo"})
        demo_cylinders=self.call("list",{"table":"cylinders"})
        self.assertTrue(any(x["name"]=="Domestic 14.2 kg" for x in demo_cylinders))
        self.assertFalse(any(x["id"]==live_cylinder for x in demo_cylinders))
        self.call("add_employee",{"name":"Demo only"})
        cleared=self.call("clear_data",{"confirmation":"CLEAR DEMO DATA"})
        self.assertTrue(cleared["backup"].startswith("demo-"))
        self.assertEqual(self.call("list",{"table":"cylinders"}),[])
        self.call("data_mode",{"mode":"live"})
        self.assertEqual([x["id"] for x in self.call("list",{"table":"cylinders"})],[live_cylinder])
        with self.assertRaises(PermissionError):
            self.call("clear_data",{"confirmation":"CLEAR LIVE DATA"},{"id":"manager","username":"manager","role":"Manager","employee_id":None})

    def test_remaining_report_queries_password_change_and_user_management(self):
        cylinder_id = self.cylinder()
        self.stock_in(cylinder_id, 3)
        employee_id = self.employee("Report Employee")
        self.call("sale", {"kind": "new_connection", "sale_date": "2026-11-19", "employee_id": employee_id, "amount": 100, "collected": 100, "items": [{"cylinder_id": cylinder_id, "quantity": 1, "unit_price": 100}]})
        session_id = self.call("open_session", {"employee_id": employee_id, "work_date": "2026-11-19", "items": [{"cylinder_id": cylinder_id, "quantity": 1}]})["id"]
        self.call("close_session", {"session_id": session_id, "closing_full": json.dumps({cylinder_id: 1}), "closing_empty": "{}", "closing_damaged": "{}", "actual_cash": 0, "verified_by": "Owner"})

        reports = ["inventory", "inventory_adjustments", "sales", "vendors", "pending", "cash", "discrepancies", "employee_performance", "employees", "advances", "expenses", "finance", "audit", "sales_trend"]
        for report_name in reports:
            with self.subTest(report=report_name):
                self.assertIsInstance(self.call("report", {"query": report_name}), list)
        statement = self.call("report", {"query": "closing_statement", "session_id": session_id})
        self.assertEqual(statement["session"]["employee"], "Report Employee")

        self.call("add_user", {"username": "report-viewer", "password": "viewer-password", "role": "Viewer"})
        self.assertIn("report-viewer", [u["username"] for u in self.call("users")])
        viewer = {"id": "test-viewer", "username": "report-viewer", "role": "Viewer", "employee_id": None}
        self.assertEqual(viewer["role"], self.call("me", user=viewer)["role"])
        with self.assertRaises(PermissionError):
            self.call("business_expense", {"category": "Rent", "amount": 1}, viewer)
        self.call("change_password", {"password": "replacement-password"})
        auth = security.AuthenticationService(database.connect, database.LOCK, database.audit)
        token = auth.login("admin", "replacement-password")
        self.assertEqual(auth.session(token)["role"], "Owner")
        auth.logout(token)
        self.call("backup")
        self.assertTrue(self.call("backups"))


if __name__ == "__main__":
    unittest.main()
