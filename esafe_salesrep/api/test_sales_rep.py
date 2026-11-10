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
            "frappe.utils": SimpleNamespace(cint=int, flt=float, escape_html=str, nowdate=Mock()),
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
