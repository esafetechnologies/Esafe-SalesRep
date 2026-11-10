"""Exercise sales-rep validation and retry identity without a Frappe site."""

import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


class ValidationError(Exception):
    pass


class DuplicateEntryError(Exception):
    pass


def raise_validation(message, error=ValidationError):
    raise error(message)


class SalesRepTests(unittest.TestCase):
    def setUp(self):
        frappe = Mock()
        frappe._ = str
        frappe.throw = raise_validation
        frappe.whitelist.return_value = lambda method: method
        frappe.DuplicateEntryError = DuplicateEntryError
        frappe.session.user = "rep@example.test"
        modules = {
            "frappe": frappe,
            "frappe.utils": SimpleNamespace(cint=int, flt=lambda value: float(value or 0), escape_html=str, nowdate=Mock()),
            "esafe_salesrep.api.permissions": Mock(),
            "esafe_salesrep.api.catalog": Mock(),
            "esafe_salesrep.api.session": Mock(),
            "esafe_salesrep.price_books": Mock(),
        }
        spec = importlib.util.spec_from_file_location("sales_rep_under_test", Path(__file__).with_name("sales_rep.py"))
        self.rep = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(self.rep)
        self.rep._sales_person = Mock(return_value=None)

    def test_numeric_validation_rejects_nonfinite_and_overpayments(self):
        for value in ("NaN", "Infinity", "not a number", 0, -1, 100.01):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.rep._number(value, "payment amount", 0.000001, 100)
        self.assertEqual(self.rep._number("100", "payment amount", 0.000001, 100), 100)

    def test_retry_returns_the_original_activity_and_rejects_changed_amount(self):
        payload = {"invoice": "SINV-1", "amount": 50}
        profile = SimpleNamespace(company="Company", name="Field Sales")
        key = "4bc06bcf-6717-4b79-b477-d1f219693ae5"
        previous = SimpleNamespace(
            owner=self.rep.frappe.session.user, action="Payment Entry", pos_profile=profile.name,
            payload_hash=hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
            reference_name="PAY-1",
        )
        reservation = Mock()
        reservation.insert.side_effect = DuplicateEntryError
        self.rep.frappe.get_doc.side_effect = [reservation, previous, reservation, previous]
        activity, replay = self.rep._reserve(profile, "Payment Entry", key, payload)
        self.assertTrue(replay)
        self.assertEqual(activity.reference_name, "PAY-1")
        with self.assertRaisesRegex(ValidationError, "different action"):
            self.rep._reserve(profile, "Payment Entry", key, dict(payload, amount=51))

    def test_check_in_rejects_out_of_range_coordinates_before_recording(self):
        self.rep._profile = Mock()
        self.rep._reserve = Mock()
        self.rep.frappe.has_permission.return_value = True
        with self.assertRaisesRegex(ValidationError, "latitude"):
            self.rep.check_in("Field Sales", 91, 79, 5, "unused")
        self.rep._reserve.assert_not_called()

    def test_native_order_discount_takes_precedence_over_negotiation(self):
        doc = SimpleNamespace(
            get=lambda field: False, discount_amount=0, additional_discount_percentage=0,
            flags=SimpleNamespace(),
        )

        def calculate(method):
            doc.total = 1000
            doc.discount_amount = doc.additional_discount_percentage * 10

        def native_rule(current):
            # A quantity or amount rule needs the item totals first.
            self.assertEqual(current.total, 1000)
            current.discount_amount = 150

        doc.run_method = calculate
        path = "erpnext.accounts.doctype.pricing_rule.utils"
        with patch.dict(sys.modules, {path: SimpleNamespace(apply_pricing_rule_on_transaction=native_rule)}):
            self.rep._apply_pricing(doc, 5)
        self.assertEqual(doc.discount_amount, 150)
        self.assertEqual(doc.flags.sales_rep_automatic_discount, 150)
        self.assertEqual(doc.additional_discount_percentage, 0)

    def test_negotiation_applies_when_there_is_no_automatic_order_discount(self):
        doc = SimpleNamespace(
            get=lambda field: False, discount_amount=0, additional_discount_percentage=0,
            flags=SimpleNamespace(),
        )

        def calculate(method):
            doc.discount_amount = doc.additional_discount_percentage * 10

        doc.run_method = calculate
        path = "erpnext.accounts.doctype.pricing_rule.utils"
        with patch.dict(sys.modules, {path: SimpleNamespace(apply_pricing_rule_on_transaction=lambda current: None)}):
            self.rep._apply_pricing(doc, 5)
        self.assertEqual(doc.discount_amount, 50)
        self.assertEqual(doc.flags.sales_rep_automatic_discount, 0)

    def test_changed_item_price_is_rejected_even_when_rounded_total_matches(self):
        class Row(dict):
            __getattr__ = dict.__getitem__

        item = Row(item_code="ITEM", item_name="Item", qty=1, uom="Nos", rate=100.15,
                   amount=100.15, discount_percentage=0)
        doc = SimpleNamespace(name=None, currency="LKR", net_total=100.15, total_taxes_and_charges=0,
                              rounded_total=100, discount_amount=0, flags={}, items=[item],
                              is_rounded_total_disabled=lambda: False)
        reviewed = self.rep._totals(doc)
        item["rate"] = item["amount"] = doc.net_total = 100.25
        with self.assertRaisesRegex(ValidationError, "recalculated"):
            self.rep._verify_reviewed_pricing(doc, {
                "reviewed_currency": "LKR", "reviewed_total": 100, "reviewed_pricing": reviewed["pricing_signature"],
            })
