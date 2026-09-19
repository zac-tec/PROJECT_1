# GST-inclusive sales and customer payments

The owner confirmed on 17 September 2026 that every existing August and September sale, including imported historical quantities and four saved invoices, should be priced at Rs. 8.40 including 12% GST. Base value is Rs. 7.50 and GST Rs. 0.90 per brick. Existing payment amounts and brick quantities are preserved. Original saved invoice records are retained in sale_price_revision_audit; a database backup precedes the one-off correction.

New manager sales require an explicitly entered GST-inclusive price; no brick price is prefilled. Current implementation uses the owner's specified 12% GST for invoices, including any added sale charges, rounded on the total invoice. The receipt shows inclusive unit rate, base unit rate, taxable value, included GST and gross total. It remains a sales receipt; this change does not add GSTIN/HSN/place-of-supply fields or implement statutory return filing or input-tax-credit accounting.

Monthly sales revenue, revenue trends and profit calculations exclude sales GST. Collections and balances use the gross bill. Historical payment details remain unknown. Production cost estimates continue using saved material/charge costs; no purchase GST/ITC has been inferred or stripped out.

Admin → Brick Sales → All Sales → Mark paid records the remaining balance as collected, after confirmation. Green means fully paid; red means outstanding. Settlement locks the invoice, checks the expected balances and writes sale_payment_audit. Repeating it cannot add another payment. The manager cannot edit invoices already settled by admin. Payment status changes do not alter stock, billed revenue or profit. Customer lookup totals refresh from invoices.

Profit results show a green Profit or red Loss label and amount. Fixed expenses and unknown opening-batch cost assumptions still apply; collection is distinct from profit.

Migrations: migration_sale_payments.sql and migration_sales_gst.sql (startup). Unit test: python -m unittest discover -s tests -p test_sales_tax.py. Integration verified with rollback: repricing without changing payments, GST splitting, net revenue, stale settlement rejection, repeated settlement, manager edit protection and no stock change on payment.

## Optional transportation (19 September)

New sales support no separate transport charge, a per-brick transport rate, or one flat transport charge. Keep the brick price separate: 1,000 × ₹8.40 plus 1,000 × ₹0.75 transport is ₹9,150; a flat ₹500 transport charge instead totals ₹8,900. Other charges remain separate. All entered charges retain the app's existing GST-inclusive calculation; transport is included in the billed total and customer balance, with its own receipt line. This does not record a transporter expense or infer a transport cost.

`transport_mode`, `transport_rate` and computed `transport_amount` are saved on each new sale. Existing invoices and historical sales are not repriced, and their original transport details remain unknown. Edits restore the saved transport selection; outdated clients cannot silently remove saved transport. Request retry matching includes transport values. Startup applies `migration_sale_transport.sql`. Focused tests are in `test_transport.py`; save/edit/receipt/ledger behaviour was verified on an isolated database copy.
