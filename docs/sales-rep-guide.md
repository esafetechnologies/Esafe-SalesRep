# Esafe-SalesRep

Open `/pos` on the ERPNext site. The register interface is available at `/pos#/till`.

## Install the app

Frappe identifies the app as `esafe_salesrep` and displays **Esafe-SalesRep**.
On a fresh site with ERPNext installed, run:

```sh
bench get-app https://github.com/esafetechnologies/Esafe-SalesRep
bench --site <site> install-app esafe_salesrep
```

For an existing deployment from before this rename, back up the site and sync
queued register transactions on every device before switching. This release has
a new app ID, module, roles, and custom field names. Plan and test the transfer of
existing settings, role assignments, and app-specific records on a restored
backup. A regular Bench update does not transfer them. Update integrations to
use `esafe_salesrep.api.*` after the switch.
Companion apps that call the previous API namespace need a matching update.
The optional reporting dashboard also requires a companion release that provides
the `lumen_reports.integrations.esafe_salesrep` contract.

## Set up a rep

1. Run `bench --site <site> migrate` for updates to an installation already using the `esafe_salesrep` app ID.
2. Assign an enabled POS Profile with the rep's company, warehouse, selling price list, taxes, and any item group restrictions. The profile supplies defaults without requiring a register shift.
3. Give reps ERPNext access to the company, items, customers, and the documents they work with. Creating a quotation, invoice, or payment requires ERPNext create and submit permissions on that document type. Link a Sales Person through the rep's active Employee record to populate the sales team where the document supports it.
4. Set up selling Item Prices, Brand values, and Item images in ERPNext. For payment collection, add enabled Modes of Payment to the profile and map each to the company's cash or bank ledger account. Bank payments require a transaction reference.

## Work in the field

- **Catalog.** Search by item name or code, filter by brand and item group, enlarge item photos, and check the selling list price. On a phone, tap **View sale** after adding an item. Use **Review total** after selecting a customer and quantities to see ERPNext's final item prices, offers, taxes, and total.
- **Quotations.** Select **Quotation**, optionally enter a validity date, and submit. Open the document in ERPNext to use the standard quotation-to-sales-order workflow, or use **Print** to share a copy.
- **Invoices.** Select **Invoice**, choose a due date if needed, and submit. The invoice posts on account. Fulfil stock through ERPNext's delivery workflow. The Invoices tab shows status, balances, and due dates, with filters for outstanding invoices, sold item code, and brand.
- **Negotiation.** Add an extra percentage discount before reviewing the total. An automatic ERPNext order discount takes precedence over the extra discount. Automatic item discounts can combine with an extra discount when no automatic order discount applies. Esafe-SalesRep price-edit access and configured discount limits apply to negotiation. Passcode-enabled policies accept a manager passcode. If the policy requires a remote approval request, handle the exception in ERPNext.
- **Payments.** Open an outstanding invoice and record the amount actually received. A partial Payment Entry reduces the balance and leaves the rest due. Use ERPNext Desk for cross-currency receipts, payment-term allocations, early-payment discounts, or collection by another user.
- **Activity.** Select **Check in with location** to save your current coordinates and estimated accuracy with the server timestamp. This requires HTTPS and browser location permission. The activity log also records who submitted documents and payments. Authorized Esafe-SalesRep managers can switch to team activity for the selected profile. Location is collected only when a rep checks in.

The workspace needs an active ERPNext connection for catalog and transaction data. If a transaction response is lost, use **Retry request** while the page is open. This reuses the same request key to avoid creating a duplicate.

## Check pricing before rollout

On a staging site, use the same company, customer, warehouse, price list, item
UOM, quantities, and tax settings in Sales Rep and ERPNext Desk. Compare both
the reviewed and submitted line prices, taxes, and rounded total. Exercise the
pricing rules the site uses, including an eligible and ineligible order for
each quantity threshold. Where configured, include a brand discount, a
customer group price list, a whole-order discount, and a promotional item. Test
a partial payment against a submitted invoice and verify its remaining balance
in ERPNext.
