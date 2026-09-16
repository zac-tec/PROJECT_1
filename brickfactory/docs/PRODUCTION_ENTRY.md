# Production dates and missing-entry popup

Admin → Settings → Manager production entry sets how many previous days the manager may enter. Default: 1 (today and yesterday); 0 means today only. Manager → Production → Production date selects the day before preview/save. The API checks the limit again on save, so a stale page cannot bypass an admin change. Future dates and finalized opening-stock dates are rejected. Existing entries require confirmation to overwrite and apply only the quantity difference.

On this installation the opening-stock import was finalized through 12 September 2026; the earliest daily-entry date is 13 September, even if a larger allowance is configured. Changing older imported history requires separate stock reconciliation.

The selected date controls production, batch age/curing, material-rate lookup and daily cost snapshot. Corrections reuse the day's cost snapshot. A newly entered past day uses the currently configured recipe and making charges with the material rates effective on that day; historical recipe versions are not available. Materials are deducted from current available inventory when saved. The batch movement is effective at the end of the selected past day; its reason and production_submission_audit preserve the actual recording time. No production time is inferred from the date selector.

A missing-production popup checks the logged-in account on page load, return to the app and each minute. From the configured daily report email time until midnight IST, Monday–Saturday, managers are asked to enter today's production and admins see that it is missing. Dismissal lasts for the current login session/date. Saving today's production suppresses it; saving a previous date does not count for today. The popup does not need notification permission. Existing push reminders remain independently configured.

Tests: `python -m unittest discover -s tests -p test_production_entry_policy.py -v`. Migration: `migration_production_entry.sql`, applied during startup.
