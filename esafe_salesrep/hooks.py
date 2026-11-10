# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
# "Esafe-SalesRep" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
app_name = "esafe_salesrep"
app_title = "Esafe-SalesRep"
app_publisher = "Esafe (PVT) LTD"
app_description = "Field sales, quotations, invoicing, and payments for ERPNext"
app_email = "hello@esafe.lk"
app_license = "AGPL-3.0-only"

required_apps = ["erpnext"]

# Frappe's apps screen opens the field sales workspace for users with sales access.
# The Frappe 16 desk tile and sidebar are the files in desktop_icon/ and
# workspace_sidebar/, which Frappe 16 imports on every migrate.
add_to_apps_screen = [
    {
        "name": app_name,
        "logo": "/assets/esafe_salesrep/pos/icon-192.png",
        "title": app_title,
        "route": "/pos",
        "has_permission": "esafe_salesrep.api.sales_rep.can_open_workspace",
    }
]

after_install = "esafe_salesrep.install.after_install"

# The Esafe-SalesRep Stock app (0.68.0): before a stock count is submitted in the desk,
# what moved after it was counted and what open shifts still hold.
doctype_js = {"Stock Reconciliation": "public/js/stock_reconciliation.js"}
# Runs on every app update (Frappe Cloud deploy), keeps the Esafe-SalesRep roles and
# custom fields in place on existing sites without shell access.
after_migrate = "esafe_salesrep.install.ensure_setup"

# Self-healer: re-drive any register shift stuck in "Closing" (a consolidation
# that timed out or failed) toward "Closed", serialized so it never collides
# with a live close. This is the backstop that guarantees no shift is ever left
# half-closed for the next cashier to stumble into.
scheduler_events = {
    "cron": {
        "*/10 * * * *": [
            "esafe_salesrep.api.register.reconcile_stuck_closings",
        ],
        # Forgotten-shift alert. Hourly is enough, it emails once per shift
        # (de-duped by the session's overdue_notified flag) and never closes a
        # till, so it can't race anything.
        "0 * * * *": [
            "esafe_salesrep.api.register.notify_overdue_sessions",
        ],
        # Cashback, once a day and in this order: write off what expired, then
        # book the days that have ended to the accounts (one summary Journal
        # Entry per company, day and outlet cost center). One job so the two
        # steps can never run out of order.
        "30 0 * * *": [
            "esafe_salesrep.cashback.nightly",
        ],
        # Customer balances spent across companies of a group: yesterday's
        # lines booked as Inter Company Journal Entry pairs (one per day, pair
        # of companies and kind of balance).
        "45 0 * * *": [
            "esafe_salesrep.inter_company.nightly",
        ],
        # Other currencies set to Automatic: the day's published rate, less the
        # shop's margin, saved as ERPNext Currency Exchange.
        "15 0 * * *": [
            "esafe_salesrep.currency.daily_rates",
        ],
    },
}

# Demo builder only (esafe_salesrep/demo_data.py). Dates the documents of a demo
# history through Frappe's own hook instead of patching the framework at
# runtime. It returns at once unless a demo run has set
# frappe.flags.esafe_salesrep_demo_stamp, so a real sale is never touched.
doc_events = {
    "POS Invoice": {
        "before_insert": "esafe_salesrep.demo_data.apply_demo_stamp",
        # ERPNext 16 leaves loyalty points owing on a POS Invoice (see there).
        "before_submit": "esafe_salesrep.erpnext_compat.settle_points_outstanding",
    },
    "Sales Invoice": {
        "before_insert": [
            "esafe_salesrep.demo_data.apply_demo_stamp",
            # The close's merged invoice keeps no "paid in" figures (esafe_salesrep.paid_in).
            "esafe_salesrep.paid_in.clear_on_merged",
        ],
    },
    "Stock Entry": {"before_insert": "esafe_salesrep.demo_data.apply_demo_stamp"},
    # A deleted merged count gives its shared count back (esafe_salesrep.api.stock_app).
    "Stock Reconciliation": {"on_trash": "esafe_salesrep.api.stock_app.on_reconciliation_trash"},
    "POS Opening Entry": {"before_insert": "esafe_salesrep.demo_data.apply_demo_stamp"},
    "POS Closing Entry": {"before_insert": "esafe_salesrep.demo_data.apply_demo_stamp"},
    "Payment Entry": {"before_insert": "esafe_salesrep.demo_data.apply_demo_stamp"},
}

# The till's service worker has to come from the site ROOT to be allowed to
# control /pos, and Frappe never serves a .js file from an app's www folder.
# This renderer answers /sw.js and nothing else (see esafe_salesrep/service_worker.py).
# v13 has no page_renderer hook, so the till there stays online-only.
page_renderer = ["esafe_salesrep.service_worker.ServiceWorkerPage"]

# The POS single-page app is served at /pos (see esafe_salesrep/www/pos.py).
# All sub-paths resolve to the same page; the frontend uses a hash router.
website_route_rules = [
    {"from_route": "/pos/<path:app_path>", "to_route": "pos"},
]
