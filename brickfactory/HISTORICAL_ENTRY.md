# One-time historical reconstruction

Open **Admin → Brick Sales → One-time historical entry → Open / reload saved session**.

1. Set the first tracked date, the date history is complete through (yesterday or earlier), and the older opening brick quantity. Confirm that opening bricks were fully cured.
2. Review the recipe snapshot. Quantities are per mix: fly ash and sand in kg, cement in bags, chemical in litres. Current-recipe estimates are not evidence of actual historical usage; enter a suitable recipe and explain its source. This session uses one recipe for the full period.
3. Add one row per date with actual mixes and bricks produced. For multiple sales, enter `2500, 1000, 2500` in the sales cell. Do not use commas as thousands separators. Enter zero production for sales-only dates.
4. Save the draft to the database. Draft saving does not alter live stock. Reload retrieves the saved session and replaces unsaved edits.
5. Preview. Rows are processed chronologically. Sales consume the oldest eligible stock, with a seven-day minimum age at the date of sale. Insufficient eligible stock blocks the reconstruction rather than creating negative batches. Material consumption is mixes multiplied by the saved recipe, including fractional quantities.
6. Apply the exact saved draft once. Application requires empty live production, sales, batch movements and finished stock. It establishes remaining dated batches and locks the session. It does not create customer invoices, invent revenue/labour/costs, or deduct historical consumption from current material inventory. The dated rows and consumption estimates remain stored in the session and visible in its preview; dated quantities also appear in stock history.
7. Enter current material balances from an actual count, and use the normal workflow for new daily production and sales.

An applied session cannot be edited or applied twice. Before any reset, take and verify a private database backup. The reset is an operator task, not an unrestricted browser button. Schema changes belong in source control; client historical entries and backups do not.

Run the calculation tests with `PYTHONPATH=. python tests/test_historical_entry.py` from the application directory.
