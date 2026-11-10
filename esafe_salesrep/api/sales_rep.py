# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
"""Field sales using ERPNext documents and the signed-in user's permissions."""

import hashlib
import json
import math
import uuid

import frappe
from frappe import _
from frappe.utils import cint, escape_html, flt, nowdate

from esafe_salesrep.api import permissions
from esafe_salesrep.api.catalog import internal_item_codes, item_groups_under
from esafe_salesrep.api.session import _user_profiles
from esafe_salesrep.price_books import get_price_map


ACTIVITY = "Sales Rep Activity"
DOCUMENTS = {"quotation": "Quotation", "invoice": "Sales Invoice"}
PAGE_SIZE = 24


def _profile(name):
    permissions.assert_outlet(name)
    profile = frappe.get_cached_doc("POS Profile", name)
    if profile.get("disabled"):
        frappe.throw(_("Select an enabled sales profile."))
    frappe.has_permission("Company", doc=profile.company, throw=True)
    return profile


def _sales_person():
    if not frappe.db.exists("DocType", "Employee"):
        return None
    employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")
    if employee:
        return frappe.db.get_value("Sales Person", {"employee": employee, "enabled": 1, "is_group": 0}, "name")


def _can_post(doctype):
    return all(frappe.has_permission(doctype, permission) for permission in ("create", "submit"))


@frappe.whitelist()
def bootstrap():
    names = _user_profiles()
    companies = frappe.get_list("Company", fields=["name", "default_currency"], limit_page_length=0)
    currencies = {row.name: row.default_currency for row in companies}
    profiles = [frappe.get_cached_doc("POS Profile", name) for name in names]
    settings = frappe.get_cached_doc("Esafe-SalesRep Settings")
    return {
        "user": frappe.session.user,
        "full_name": frappe.get_cached_value("User", frappe.session.user, "full_name"),
        "sales_person": _sales_person(),
        "profiles": [
            {"name": profile.name, "company": profile.company, "currency": currencies[profile.company]}
            for profile in profiles if profile.company in currencies
        ],
        "can_discount": permissions.can_edit_price(),
        "discount_limit": flt(settings.get("discount_limit_percent")),
        "discount_approval": settings.get("discount_approval_mode") or "Passcode only",
        "can_pay": _can_post("Payment Entry"),
        "can_view_team": permissions.is_manager(),
        "documents": {
            kind: {"read": bool(frappe.has_permission(doctype)), "post": _can_post(doctype)}
            for kind, doctype in DOCUMENTS.items()
        },
    }


def _item_filters(profile):
    filters = {"disabled": 0, "is_sales_item": 1, "has_variants": 0}
    groups = item_groups_under([row.item_group for row in profile.get("item_groups") or []])
    if groups:
        filters["item_group"] = ["in", groups]
    internal = internal_item_codes()
    if internal:
        filters["name"] = ["not in", sorted(internal)]
    return filters


def _customer(customer):
    doc = frappe.get_doc("Customer", customer)
    doc.check_permission("read")
    if doc.disabled:
        frappe.throw(_("This customer is disabled."))
    return doc


def _price_list(profile, customer=None):
    return (customer and customer.get("default_price_list")) or profile.selling_price_list


@frappe.whitelist()
def catalog(pos_profile, search="", brand="", item_group="", customer=None, start=0):
    profile = _profile(pos_profile)
    filters = _item_filters(profile)
    if brand:
        filters["brand"] = brand
    if item_group:
        allowed = filters.get("item_group")
        groups = set(item_groups_under([item_group]))
        if allowed:
            groups.intersection_update(allowed[1])
        filters["item_group"] = ["in", sorted(groups)]
    rows = frappe.get_list(
        "Item", filters=filters,
        or_filters={field: ["like", "%" + search.strip() + "%"] for field in ("item_name", "name")} if search else None,
        fields=["name", "item_name", "brand", "item_group", "stock_uom", "sales_uom", "image"],
        order_by="item_name asc, name asc", limit_start=max(cint(start), 0),
        limit_page_length=PAGE_SIZE + 1,
    )
    price_list = _price_list(profile, _customer(customer) if customer else None)
    uoms = {row.name: row.sales_uom or row.stock_uom for row in rows}
    prices = get_price_map(list(uoms), price_list, uoms, public_only=True)
    for row in rows:
        row.uom = uoms[row.name]
        row.price = prices.get(row.name)
    return {
        "items": rows[:PAGE_SIZE], "more": len(rows) > PAGE_SIZE,
        "price_list": price_list, "currency": frappe.get_cached_value("Price List", price_list, "currency") if price_list else None,
    }


@frappe.whitelist()
def catalog_filters(pos_profile):
    filters = _item_filters(_profile(pos_profile))
    return {
        field: [
            row.get(field) for row in frappe.get_list(
                "Item", filters=filters, fields=[field], group_by=field, order_by=field,
                limit_page_length=0,
            ) if row.get(field)
        ]
        for field in ("brand", "item_group")
    }


@frappe.whitelist()
def customers(pos_profile, search):
    _profile(pos_profile)
    term = "%" + search.strip() + "%"
    return frappe.get_list(
        "Customer", filters={"disabled": 0},
        or_filters={field: ["like", term] for field in ("customer_name", "name")},
        fields=["name", "customer_name"], order_by="customer_name asc", limit_page_length=20,
    )


def _number(value, label, minimum, maximum=None):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        number = float("nan")
    if not math.isfinite(number) or number < minimum or (maximum is not None and number > maximum):
        frappe.throw(_("Enter a valid {0}.").format(label))
    return number


def _document(profile, kind, payload):
    doctype = DOCUMENTS.get(kind)
    if not doctype:
        frappe.throw(_("Select a document type."))
    frappe.has_permission(doctype, "create", throw=True)
    if not payload.get("customer"):
        frappe.throw(_("Select a customer."))
    customer = _customer(payload["customer"])
    items = payload.get("items") or []
    if not isinstance(items, list) or not 1 <= len(items) <= 100:
        frappe.throw(_("Add between 1 and 100 items."))
    codes = [row["item_code"] for row in items]
    filters = _item_filters(profile)
    internal = set(filters.pop("name", ["not in", []])[1])
    filters["name"] = ["in", list(set(codes) - internal)]
    allowed = frappe.get_list("Item", filters=filters, pluck="name", limit_page_length=0)
    if set(allowed) != set(codes) or len(set(codes)) != len(codes):
        frappe.throw(_("Each item must be available in this catalog and appear once."))
    discount = _number(payload.get("discount", 0), _("discount percentage"), 0, 100)
    if discount and not permissions.can_edit_price():
        frappe.throw(_("You do not have permission to negotiate discounts."), frappe.PermissionError)

    doc = frappe.new_doc(doctype)
    doc.company = profile.company
    doc.selling_price_list = _price_list(profile, customer)
    doc.set_warehouse = profile.warehouse
    doc.taxes_and_charges = profile.taxes_and_charges
    if kind == "quotation":
        doc.quotation_to = "Customer"
        doc.party_name = customer.name
        doc.transaction_date = nowdate()
        if payload.get("document_date"):
            doc.valid_till = payload["document_date"]
    else:
        doc.customer = customer.name
        doc.posting_date = nowdate()
        doc.is_pos = 0
        doc.update_stock = 0
        if payload.get("document_date"):
            doc.due_date = payload["document_date"]
    for row in items:
        doc.append("items", {
            "item_code": row["item_code"], "qty": _number(row.get("qty"), _("quantity"), 0.000001),
            "warehouse": profile.warehouse,
        })
    sales_person = _sales_person()
    if sales_person and doc.meta.has_field("sales_team"):
        doc.append("sales_team", {"sales_person": sales_person, "allocated_percentage": 100})
    doc.set_missing_values()
    if hasattr(doc, "set_taxes_and_charges"):
        doc.set_taxes_and_charges()
    for row in doc.items:
        if not row.get("is_free_item") and flt(row.rate) <= 0 and flt(row.price_list_rate) <= 0:
            frappe.throw(_("No selling price was found for {0}. Set its price in ERPNext.").format(row.item_code))
    if discount:
        doc.apply_discount_on = "Net Total"
        doc.additional_discount_percentage = discount
    doc.run_method("calculate_taxes_and_totals")
    return doc


def _totals(doc):
    return {
        "name": doc.name, "currency": doc.currency, "net_total": doc.net_total,
        "taxes": doc.total_taxes_and_charges,
        "total": flt(doc.grand_total if doc.is_rounded_total_disabled() else doc.rounded_total),
        "discount": doc.discount_amount,
    }


@frappe.whitelist()
def preview(pos_profile, kind, payload):
    return _totals(_document(_profile(pos_profile), kind, frappe.parse_json(payload)))


def _reserve(profile, action, request_key, payload):
    # The activity row and ERP document commit together. The primary key
    # serializes duplicate requests, including after a response is lost.
    try:
        key = str(uuid.UUID(str(request_key)))
    except (ValueError, TypeError):
        frappe.throw(_("Invalid request key."))
    name = hashlib.sha256((frappe.session.user + ":" + key).encode()).hexdigest()
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    activity = frappe.get_doc({
        "doctype": ACTIVITY, "request_key": name, "payload_hash": fingerprint, "action": action,
        "company": profile.company, "pos_profile": profile.name,
        "sales_person": _sales_person(),
    })
    try:
        activity.insert(ignore_permissions=True)
    except frappe.DuplicateEntryError:
        frappe.db.rollback()
        existing = frappe.get_doc(ACTIVITY, name)
        if (existing.owner != frappe.session.user or existing.action != action
                or existing.pos_profile != profile.name or existing.payload_hash != fingerprint):
            frappe.throw(_("This request key was already used for a different action."))
        return existing, True
    return activity, False


@frappe.whitelist(methods=["POST"])
def post_document(pos_profile, kind, payload, request_key, passcode=None):
    profile = _profile(pos_profile)
    payload = frappe.parse_json(payload)
    doctype = DOCUMENTS.get(kind)
    if not doctype or not _can_post(doctype):
        frappe.throw(_("You need permission to create and submit this document."), frappe.PermissionError)
    activity, replay = _reserve(profile, doctype, request_key, payload)
    if replay:
        return {"name": activity.reference_name}
    doc = _document(profile, kind, payload)
    from esafe_salesrep.api.sales import _check_discount_passcode

    _check_discount_passcode({
        "pos_profile": profile.name, "order_discount_percent": payload.get("discount"),
        "discount_passcode": passcode,
    })
    doc.insert()
    doc.submit()
    totals = _totals(doc)
    if (totals["currency"] != payload.get("reviewed_currency")
            or totals["total"] != _number(payload.get("reviewed_total"), _("reviewed total"), 0)):
        frappe.throw(_("ERPNext recalculated the total. Review the latest price and try again."))
    note = str(payload.get("note") or "").strip()[:1000]
    if note:
        doc.add_comment("Comment", text=escape_html(note))
    activity.db_set("reference_name", doc.name)
    return {"name": doc.name}


@frappe.whitelist()
def list_documents(pos_profile, kind, search="", due_only=0, start=0, item_code="", brand="", team=0):
    profile = _profile(pos_profile)
    doctype = DOCUMENTS.get(kind)
    if not doctype:
        frappe.throw(_("Select a document type."))
    filters = {"company": profile.company, "docstatus": ["<", 2]}
    if not (cint(team) and permissions.is_manager()):
        filters["owner"] = frappe.session.user
    date_field = "posting_date" if kind == "invoice" else "transaction_date"
    fields = ["name", "owner", "customer_name", date_field, "status", "docstatus", "grand_total", "rounded_total", "currency"]
    if kind == "invoice":
        fields += ["outstanding_amount", "due_date", "debit_to"]
        filters["is_return"] = 0
        if cint(due_only):
            filters.update({"docstatus": 1, "outstanding_amount": [">", 0]})
    else:
        fields += ["valid_till"]
    filters = [
        [doctype, field, *value] if isinstance(value, list) else [doctype, field, "=", value]
        for field, value in filters.items()
    ]
    child_filters = []
    if kind == "invoice" and item_code.strip():
        child_filters.append(["Sales Invoice Item", "item_code", "like", "%" + item_code.strip() + "%"])
    if kind == "invoice" and brand:
        child_filters.append(["Sales Invoice Item", "brand", "=", brand])
    rows = frappe.get_list(
        doctype, filters=filters + child_filters, fields=fields, distinct=bool(child_filters),
        or_filters={field: ["like", "%" + search.strip() + "%"] for field in ("name", "customer_name")} if search else None,
        order_by="`tab{0}`.`{1}` desc, `tab{0}`.`name` desc".format(doctype, date_field),
        limit_start=max(cint(start), 0),
        limit_page_length=PAGE_SIZE + 1,
    )
    if kind == "invoice":
        for row in rows:
            account = row.pop("debit_to", None)
            row.outstanding_currency = frappe.get_cached_value("Account", account, "account_currency") if account else None
    return {"rows": rows[:PAGE_SIZE], "more": len(rows) > PAGE_SIZE}


def _payable_invoice(profile, name):
    doc = frappe.get_doc("Sales Invoice", name)
    doc.check_permission("read")
    if doc.company != profile.company or doc.owner != frappe.session.user:
        frappe.throw(_("This invoice is outside your sales workspace."), frappe.PermissionError)
    if doc.docstatus != 1 or doc.is_return or flt(doc.outstanding_amount) <= 0:
        frappe.throw(_("This invoice has no payable balance."))
    return doc


def _payment_accounts(profile, currency):
    accounts = {}
    for row in profile.get("payments") or []:
        mode = frappe.get_cached_doc("Mode of Payment", row.mode_of_payment)
        if not mode.enabled:
            continue
        for link in mode.accounts:
            if link.company != profile.company or not link.default_account:
                continue
            account = frappe.get_cached_doc("Account", link.default_account)
            if (account.company == profile.company and account.account_currency == currency
                    and not account.is_group and not account.disabled and account.account_type in ("Cash", "Bank")):
                accounts[mode.name] = account
    return accounts


@frappe.whitelist()
def payment_options(pos_profile, invoice):
    profile = _profile(pos_profile)
    if not _can_post("Payment Entry"):
        frappe.throw(_("You need permission to create and submit Payment Entries."), frappe.PermissionError)
    doc = _payable_invoice(profile, invoice)
    currency = frappe.get_cached_value("Account", doc.debit_to, "account_currency")
    return {
        "currency": currency, "outstanding": doc.outstanding_amount,
        "modes": [
            {"name": name, "reference_required": account.account_type == "Bank"}
            for name, account in _payment_accounts(profile, currency).items()
        ],
    }


@frappe.whitelist(methods=["POST"])
def record_payment(pos_profile, invoice, mode, amount, request_key, reference=""):
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

    profile = _profile(pos_profile)
    if not _can_post("Payment Entry"):
        frappe.throw(_("You need permission to create and submit Payment Entries."), frappe.PermissionError)
    payload = {"invoice": invoice, "mode": mode, "amount": amount, "reference": reference}
    activity, replay = _reserve(profile, "Payment Entry", request_key, payload)
    if replay:
        return {"name": activity.reference_name}
    doc = _payable_invoice(profile, invoice)
    # Serialize payments made here against the same receivable and read the
    # latest balance after acquiring the lock, even under repeatable read.
    current = frappe.db.get_value("Sales Invoice", invoice, ["outstanding_amount", "docstatus"], as_dict=True, for_update=True)
    if not current or current.docstatus != 1:
        frappe.throw(_("This invoice is no longer submitted."))
    currency = frappe.get_cached_value("Account", doc.debit_to, "account_currency")
    account = _payment_accounts(profile, currency).get(mode)
    if not account:
        frappe.throw(_("Select a payment mode with a matching cash or bank account."))
    reference = (reference or "").strip()
    if account.account_type == "Bank" and not reference:
        frappe.throw(_("Enter the bank or transaction reference."))
    amount = _number(amount, _("payment amount"), 0.000001, flt(current.outstanding_amount))
    entry = get_payment_entry("Sales Invoice", invoice, bank_account=account.name)
    if len(entry.references) != 1 or entry.references[0].get("payment_term") or entry.deductions:
        frappe.throw(_("Record this payment in ERPNext to apply its payment terms or discounts."))
    if entry.paid_from_account_currency != currency or entry.paid_to_account_currency != currency:
        frappe.throw(_("Record this cross-currency receipt in ERPNext."))
    entry.mode_of_payment = mode
    entry.reference_no = reference
    entry.reference_date = nowdate()
    entry.paid_amount = entry.received_amount = flt(amount, entry.precision("paid_amount"))
    if entry.paid_amount <= 0 or entry.paid_amount > flt(current.outstanding_amount):
        frappe.throw(_("The rounded amount must be positive and within the outstanding balance."))
    entry.references[0].allocated_amount = entry.paid_amount
    entry.references[0].outstanding_amount = current.outstanding_amount
    entry.insert()
    entry.submit()
    activity.db_set("reference_name", entry.name)
    activity.db_set("related_invoice", doc.name)
    return {"name": entry.name}


@frappe.whitelist(methods=["POST"])
def check_in(pos_profile, latitude, longitude, accuracy, request_key):
    profile = _profile(pos_profile)
    if not (frappe.has_permission("Quotation", "create") or frappe.has_permission("Sales Invoice", "create")):
        frappe.throw(_("You need sales document access to check in."), frappe.PermissionError)
    location = {
        "latitude": _number(latitude, _("latitude"), -90, 90),
        "longitude": _number(longitude, _("longitude"), -180, 180),
        "accuracy": _number(accuracy, _("location accuracy"), 0),
    }
    activity, replay = _reserve(profile, "Check-in", request_key, location)
    if not replay:
        activity.db_set(location)
    return {"creation": activity.creation}


@frappe.whitelist()
def list_activity(pos_profile, team=0, start=0):
    profile = _profile(pos_profile)
    filters = {"pos_profile": profile.name}
    if not (cint(team) and permissions.is_manager()):
        filters["owner"] = frappe.session.user
    rows = frappe.get_all(
        ACTIVITY, filters=filters,
        fields=["name", "creation", "owner", "sales_person", "action", "reference_name", "related_invoice", "latitude", "longitude", "accuracy"],
        order_by="creation desc, name desc", limit_start=max(cint(start), 0),
        limit_page_length=PAGE_SIZE + 1,
    )
    return {"rows": rows[:PAGE_SIZE], "more": len(rows) > PAGE_SIZE}


def can_open_workspace():
    return any(frappe.has_permission(doctype) for doctype in DOCUMENTS.values())
