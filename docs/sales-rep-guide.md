# Esafe Sales Rep

Open `/pos` on the ERPNext site. The register interface is available at `/pos#/till`.

## Set up a rep

1. Run `bench --site <site> migrate` when deploying this version. Migration creates the Sales Rep Activity DocType.
2. Assign an enabled POS Profile with the rep's company, warehouse, selling price list, taxes, and any item group restrictions. The profile supplies defaults without requiring a register shift.
3. Give reps ERPNext access to the company, items, customers, and the documents they work with. Creating a quotation, invoice, or payment requires ERPNext create and submit permissions on that document type. Link a Sales Person through the rep's active Employee record to populate the sales team where the document supports it.
4. Set up selling Item Prices, Brand values, and Item images in ERPNext. For payment collection, add enabled Modes of Payment to the profile and map each to the company's cash or bank ledger account. Bank payments require a transaction reference.

## Work in the field

- **Catalog.** Search by item name or code, filter by brand and item group, enlarge item photos, and check the selling list price. Use **Review total** after selecting a customer and quantities to calculate the document with ERPNext pricing rules and taxes.
- **Quotations.** Select **Quotation**, optionally enter a validity date, and submit. Open the document in ERPNext to use the standard quotation-to-sales-order workflow, or use **Print** to share a copy.
- **Invoices.** Select **Invoice**, choose a due date if needed, and submit. The invoice posts on account. Fulfil stock through ERPNext's delivery workflow. The Invoices tab shows status, balances, and due dates, with filters for outstanding invoices, sold item code, and brand.
- **Negotiation.** Add an extra percentage discount before reviewing the total. LumenPOS price-edit access and configured discount limits apply. Passcode-enabled policies accept a manager passcode. If the policy requires a remote approval request, handle the exception in ERPNext.
- **Payments.** Open an outstanding invoice and record the amount actually received. A partial Payment Entry reduces the balance and leaves the rest due. Use ERPNext Desk for cross-currency receipts, payment-term allocations, early-payment discounts, or collection by another user.
- **Activity.** Select **Check in with location** to save your current coordinates and estimated accuracy with the server timestamp. This requires HTTPS and browser location permission. The activity log also records who submitted documents and payments. Authorized LumenPOS managers can switch to team activity for the selected profile. Location is collected only when a rep checks in.

The workspace needs an active ERPNext connection for catalog and transaction data. If a transaction response is lost, use **Retry request** while the page is open. This reuses the same request key to avoid creating a duplicate.
