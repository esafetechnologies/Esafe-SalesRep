# Esafe-SalesRep changelog

Start here for the current workflow, recent changes, and steps that affect deployment. For permissions, payment account setup, and detailed instructions, see the [Sales Rep setup and workflow guide](docs/sales-rep-guide.md).

## How it works today

| Where | What the rep does | What ERPNext records |
| --- | --- | --- |
| **Catalog** at `/pos` | Search by item name or code, filter by brand or item group, open product photos, and check list prices. | Products, photos, and prices come from ERPNext. |
| **New sale** | Select a customer, add items, and review ERPNext's item prices, promotions, and total. Choose **Quotation** or **Invoice** before submitting. | A Quotation or Sales Invoice with ERPNext prices and taxes. An automatic order discount takes precedence over a negotiated discount. |
| **Invoices** | Filter by outstanding balance, item code, or brand. Open an invoice and record money received. | A Payment Entry reduces the invoice balance. Any unpaid amount stays due. |
| **Activity** | Check in with location when visiting a customer. Managers can view team activity for the selected profile. | Each check-in records the rep, server time, and device location. Document submissions and payments also appear in activity. |

The Sales Rep workspace uses an enabled POS Profile for company, warehouse, and selling defaults. It requires an ERPNext connection. Invoices post on account, and stock fulfilment is handled through ERPNext. Location check-ins require HTTPS and browser permission. The original register is at `/pos#/till`.

## Unreleased

- **2026-11-10** — Improved phone and tablet use with a persistent **View sale** button, larger touch controls, and invoice cards on narrow screens. Pricing review now uses ERPNext's whole-order rules, shows line discounts and promotional items, and checks reviewed prices before posting. Sales also use the ERPNext customer or customer group price list when configured. Version 0.71.1 refreshes cached assets on existing devices. On CBT's deployed build, a live 15% brand rule reduced LKR 655.00 to LKR 556.75 on both quotation and invoice previews. The updated build passed 50 Python tests and mock browser checks at 360, 390, 768, and 1024 pixels. Confirm whole-order rules and posting on staging using the [pricing rollout checks](docs/sales-rep-guide.md#check-pricing-before-rollout).
- **2026-11-10** — Added this changelog and linked it from the README. Repository instructions now require an entry with each update.

## 0.71.0 — App identity rename

- ERPNext displays **Esafe-SalesRep** and identifies the app as `esafe_salesrep`. The package, module, DocTypes, roles, custom fields, API namespace, browser storage keys, and built assets use the new name.
- **Deployment** — Use `bench --site <site> install-app esafe_salesrep` for a fresh installation after fetching the app. An older deployment needs a tested data transfer before switching identities. Back up the site, sync queued register transactions, and update integrations to `esafe_salesrep.api.*`. Follow the [installation and migration notes](docs/sales-rep-guide.md#install-the-app).
- **Verification** — The production build, 47 Python tests, endpoint checks, and mock browser tests passed. Live ERPNext deployment remains unverified.

## 0.70.0 — Sales Rep workspace

- Made `/pos` the field sales workspace, with the original register available at `/pos#/till`.
- Added product photos and filters, quotations, invoices on account, negotiated discounts, partial payments, and activity tracking with explicit location check-ins.
- **Deployment** — The release adds the Sales Rep Activity DocType. Site setup also requires rep permissions, POS Profiles, and payment account mappings.
- **Verification** — The production build, Python tests, and desktop and mobile browser checks passed against a mock ERPNext API.
