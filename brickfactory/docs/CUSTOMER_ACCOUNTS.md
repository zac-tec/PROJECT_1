# Customer accounts

Admin → Customer Accounts contains named accounts, invoice history and a signed transaction ledger. A name or phone is required; both are not mandatory. A stable customer ID links sales. Normalized phone matches are reused (including Indian +91 formatting); name-only creation reuses an unambiguous matching name. Customers with identical names and different phone numbers remain separate. Select the existing account to avoid creating an unintended duplicate.

Managers can select an account or create a new customer while recording a sale. They can record money received with that sale, but cannot post standalone payments, refunds, balance reconciliations or reversals. Same-day sale correction retains the existing account and is blocked after admin payment activity; prior invoice values are audited.

Admin payments settle the oldest unpaid amounts first, then leave excess credit. Outstanding opening balances have priority over invoices. Credit is automatically available for the next purchase. Refunds cannot exceed available credit. Payment corrections reverse an existing entry with a reason, then the admin can post a replacement; the original remains visible. Invoice bill/GST revenue and stock do not change when a payment is posted.

“Set complete current balance” means the complete debt or credit INCLUDING saved invoices, not an extra opening debt. The system computes target minus current balance and appends that reconciliation, retaining the previous and target balances in its note. Repeating the same target does not double-count debt. Positive balance means customer owes factory; negative means factory owes customer. Zero-balance accounts are retained.

Migration runs once for each unlinked existing invoice. It creates/reuses customer accounts and imports the invoice and its recorded payment total exactly once. Imported payment timing may be unknown; its invoice date is used and the import note identifies that limitation. Anonymous imported historical quantities are not assigned to invented customers and do not become fabricated debts. Add any customer-specific confirmed balance using complete-balance reconciliation.

`brick_sales.amount_received` retains money collected with a sale. `amount_paid` becomes money/credit allocated to the invoice, capped at its gross total. `customer_ledger` is authoritative for account balance and cash movements. Monthly collections use dated ledger money movements, including later payments/refunds, rather than treating allocations to old invoices as newly received cash. Balance reconciliations are not cash or revenue. Migration and corrections keep original data/audit records.

Mutations lock the account and allocate in a database transaction. Payment submissions have UUID retry keys; repeated submissions do not collect twice. New sales also use retry keys. The old “mark this invoice paid” API is disabled; use account-level payment recording.

Migrations: `migration_customer_accounts.sql` and `customer_accounts.migrate_accounts()` at startup. Tests: `python -m unittest discover -s tests -p test_customer_allocations.py`. Rollback integration covers migration conservation, both requested FIFO scenarios, credit, refund limits, reversals, reconciliation, retry safety and unchanged revenue/stock after payments.
