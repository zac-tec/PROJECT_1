# Sales pricing — 22 September 2026

New manager sales support two pre-GST pricing methods with a debounced live backend preview:

- `brick_base`: quantity × entered brick rate, plus transport and other charges.
- `delivered_base`: quantity × agreed delivered rate already includes transport. Subtract the driver charge to identify brick revenue; do not add transport twice. Other charges remain additional.

GST is 12% of the complete pre-GST invoice subtotal, rounded half-up to paise. Transport and other GST components are rounded to paise; the brick GST component takes any residual paise so displayed components reconcile exactly. Never calculate the invoice from rounded derived per-brick rates.

Reference: 2,500 × ₹8.17 = ₹20,425 before GST; driver ₹2,200; bricks ₹18,225 (₹7.29 each); transport ₹0.88 each; GST ₹2,451; total ₹22,876. Entering ₹7.29 in brick-price mode gives the same invoice.

`price_sale` is shared by preview and persistence. Preview requests never modify data or disable typing, and stale responses cannot enable saving or overwrite newer results. Both save routes recompute totals server-side. Delivered value must exceed the driver charge.

Existing inclusive columns remain compatible with older reports. New explicit columns store pricing mode, entered rate, brick base amount, driver base amount and other base amount. Profit revenue and sales-trend revenue subtract the explicit driver base amount from taxable revenue; invoice totals and customer ledger entries still include transport and GST. No separate automatic driver expense is posted.

Old sales retain their original totals and `legacy_inclusive` mode. Old browser drafts retain inclusive interpretation. When correcting an old bill, choose a pre-GST mode, enter the actual agreed values, review the live total and save. Existing date-window and settled-invoice restrictions still apply. Audit and customer-ledger correction mechanisms are preserved. Older clients cannot overwrite a new pre-GST invoice using inclusive mode.

Receipts show pre-GST brick and transport lines and their GST. Old receipts retain their original format.

Validation: focused arithmetic/schema/transport tests, Node preview race test, isolated PostgreSQL restore with migration rerun, create/edit/retry and customer-balance assertions, and PDF generation. Deployment backed up code/database, restarted the API, and verified public health, updated frontend assets and authentication protection. No production sales were created or edited during verification.
