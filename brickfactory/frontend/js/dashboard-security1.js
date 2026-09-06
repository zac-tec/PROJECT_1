/*
  Dashboard rendering. Charts are destroyed and rebuilt each time the
  Dashboard section is opened, so switching tabs and coming back doesn't
  stack duplicate charts on the same canvas.
*/
let dashboardCharts = {};

function destroyDashboardCharts() {
  Object.values(dashboardCharts).forEach((c) => c && c.destroy());
  dashboardCharts = {};
}

const CHART_COLORS = {
  brick: "#b3542c",
  clay: "#d9a06b",
  ok: "#2f7d4f",
  bad: "#b3392c",
  muted: "#7a6f66",
};

async function loadDashboard(markSeen = true) {
  destroyDashboardCharts();
  await Promise.all([
    loadTodayActivity(markSeen),
    loadDailyProductionChart(),
    loadMonthlyTrendChart(),
    loadProfitTrendChart(),
    loadCostBreakdownChart(),
    loadStockRunwayChart(),
    loadSalesTrendChart(),
    loadTopCustomers(),
  ]);
}

// -------------------- Today's Activity --------------------
// markSeen=false is used for the silent initial page-load check, so
// opening the app doesn't instantly clear the notification badge before
// the admin has actually noticed it — only an explicit click on the
// Dashboard tab (or manual refresh while already there) clears it.
async function loadTodayActivity(markSeen = true) {
  try {
    const d = await apiFetch("/admin/dashboard/today-activity");
    const out = document.getElementById("todayActivityOutput");

    let sections = [];

    // Production
    if (d.production) {
      const p = d.production;
      sections.push(`
        <h2 style="margin-top:16px;">🏭 Production</h2>
        ${kvTable([
          { label: "Saved At", value: formatTime12(p.timestamp) },
          { label: "Mixes", value: p.mixes },
          { label: "Bricks Produced", value: p.bricks_produced, bold: true },
          { label: "Labourers", value: p.labourers },
          { label: "Misc Expense", value: `${money(p.misc_amount)} (${p.misc_note || "—"})` },
        ])}
        ${p.is_corrected === "yes" ? '<p style="color:var(--muted);"><em>Corrected today.</em></p>' : ""}
      `);
    } else {
      sections.push(`<h2 style="margin-top:16px;">🏭 Production</h2><p style="color:var(--muted);">No production entry logged yet today.</p>`);
    }

    // Sales
    if (d.sales.count > 0) {
      sections.push(`
        <h2 style="margin-top:16px;">🧱 Brick Sales</h2>
        ${kvTable([
          { label: "Sales Made", value: d.sales.count },
          { label: "Bricks Sold", value: d.sales.total_bricks },
          { label: "Revenue Billed", value: money(d.sales.total_revenue) },
          { label: "Amount Collected", value: money(d.sales.total_paid), bold: true },
        ])}
      `);
    } else {
      sections.push(`<h2 style="margin-top:16px;">🧱 Brick Sales</h2><p style="color:var(--muted);">No sales recorded yet today.</p>`);
    }

    // Stock adjustments
    if (d.stock_adjustments.length > 0) {
      const rows = d.stock_adjustments.map((a) => {
        const color = a.change_amount > 0 ? "var(--ok)" : "var(--bad)";
        return `<tr><td>${formatTime12(a.time)}</td><td style="color:${color};">${a.change_amount > 0 ? "+" : ""}${a.change_amount}</td><td>${textHTML(a.note || "—")}</td><td>${a.resulting_stock}</td></tr>`;
      }).join("");
      sections.push(`
        <h2 style="margin-top:16px;">📦 Stock Adjustments</h2>
        <table><thead><tr><th>Time</th><th>Change</th><th>Note</th><th>Resulting Stock</th></tr></thead><tbody>${rows}</tbody></table>
      `);
    }

    // Rate changes
    if (d.rate_changes.length > 0) {
      const rows = d.rate_changes.map((r) => `<tr><td>${formatTime12(r.time)}</td><td>${r.material}</td><td>${money(r.old_rate)}</td><td>${money(r.new_rate)}</td></tr>`).join("");
      sections.push(`
        <h2 style="margin-top:16px;">💰 Rate Changes</h2>
        <table><thead><tr><th>Time</th><th>Material</th><th>Old</th><th>New</th></tr></thead><tbody>${rows}</tbody></table>
      `);
    }

    // Making charge changes
    if (d.charge_changes.length > 0) {
      const rows = d.charge_changes.map((c) => `<tr><td>${formatTime12(c.time)}</td><td>${c.charge_name}</td><td>${money(c.old_value)}</td><td>${money(c.new_value)}</td></tr>`).join("");
      sections.push(`
        <h2 style="margin-top:16px;">📋 Making Charge Changes</h2>
        <table><thead><tr><th>Time</th><th>Charge</th><th>Old</th><th>New</th></tr></thead><tbody>${rows}</tbody></table>
      `);
    }

    out.innerHTML = sections.join("");
    // New activity uses textContent so names and details never become HTML.
    const heading = document.createElement("h2");
    heading.textContent = "Bills & Raw Material Receipts";
    out.append(heading);
    for (const bill of d.updated_bills || []) {
      const line = document.createElement("p");
      line.textContent = `${bill.bill_type} · ${bill.month}: ${money(bill.amount)} — saved at ${formatTime12(bill.time)}`;
      out.append(line);
    }
    for (const event of d.operational_events || []) {
      const line = document.createElement("p");
      const detail = event.details;
      line.textContent = event.type === "material_refill"
        ? `${formatTime12(event.time)} · ${event.actor} received ${detail.added} ${detail.unit} ${detail.material}. Stock after receipt: ${detail.new_total} ${detail.unit}.`
        : `${formatTime12(event.time)} · ${event.actor} ${detail.previous_amount === null ? "saved" : "updated"} ${detail.bill_type} for ${detail.month}: ${money(detail.amount)}${detail.previous_amount === null ? "" : ` (previously ${money(detail.previous_amount)})`}.`;
      out.append(line);
    }
    if (!(d.updated_bills || []).length && !(d.operational_events || []).length) {
      const empty = document.createElement("p");
      empty.textContent = "No utility bills or raw-material receipts recorded today.";
      out.append(empty);
    }

    // Mark today's activity as "seen" now that the admin has actually
    // opened the Dashboard — clears the sidebar badge.
    if (markSeen) localStorage.setItem(`activitySeen-${d.date}`, String(d.activity_count));
    updateDashboardBadge(d.activity_count, d.date);
  } catch (e) { showMessage(msgEl, e.message, true); }
}

// Checks activity count against what's been "seen" today and shows/hides
// the red badge on the Dashboard sidebar button accordingly. Called both
// on page load (so the badge is visible even if admin lands elsewhere)
// and after loadTodayActivity() marks things as seen.
function updateDashboardBadge(currentCount, dateStr) {
  const seenCount = parseInt(localStorage.getItem(`activitySeen-${dateStr}`) || "0", 10);
  const badge = document.getElementById("dashboardBadge");
  const unseen = currentCount - seenCount;
  if (unseen > 0) {
    badge.textContent = unseen;
    badge.classList.remove("hidden");
  } else {
    badge.classList.add("hidden");
  }
}

// Lightweight check used on page load, before the admin necessarily
// opens the Dashboard tab — just enough to light up the badge.
async function checkDashboardBadgeOnLoad() {
  try {
    const d = await apiFetch("/admin/dashboard/today-activity");
    updateDashboardBadge(d.activity_count, d.date);
  } catch (e) { /* silent — badge just won't show if this fails */ }
}


// -------------------- Fun Facts --------------------
async function loadFunFacts() {
  try {
    const d = await apiFetch("/admin/dashboard/fun-facts");
    document.getElementById("fact-totalBricks").textContent = d.total_bricks_produced_all_time.toLocaleString("en-IN");
    document.getElementById("fact-houses").textContent = d.houses_equivalent.toLocaleString("en-IN");
    document.getElementById("fact-streak").textContent = d.longest_work_streak_days;
    document.getElementById("fact-crew").textContent = d.avg_crew_size;
    document.getElementById("fact-sold").textContent = d.total_bricks_sold_all_time.toLocaleString("en-IN");
    document.getElementById("fact-pending").textContent = money(d.pending_customer_dues);
    if (d.best_day.date) {
      document.getElementById("fact-bestday").textContent =
        `🏅 Best day yet: ${d.best_day.date} — ${d.best_day.mixes} mixes, ${d.best_day.bricks.toLocaleString("en-IN")} bricks`;
    }
  } catch (e) { showMessage(msgEl, e.message, true); }
}

// -------------------- Daily Production (line) --------------------
async function loadDailyProductionChart() {
  try {
    const d = await apiFetch("/admin/dashboard/daily-production?days=30");
    const labels = d.days.map((r) => r.date.slice(5)); // MM-DD
    const bricks = d.days.map((r) => r.bricks);
    dashboardCharts.daily = new Chart(document.getElementById("chartDailyProduction"), {
      type: "line",
      data: { labels, datasets: [{ label: "Bricks Produced", data: bricks, borderColor: CHART_COLORS.brick, backgroundColor: CHART_COLORS.clay, tension: 0.25, fill: true }] },
      options: { responsive: true, plugins: { legend: { display: false } } },
    });
  } catch (e) { showMessage(msgEl, e.message, true); }
}

// -------------------- Monthly Trend (bar) --------------------
async function loadMonthlyTrendChart() {
  try {
    const d = await apiFetch("/admin/dashboard/monthly-trend?months=6");
    const labels = d.months.map((r) => r.month);
    const bricks = d.months.map((r) => r.total_bricks);
    dashboardCharts.monthly = new Chart(document.getElementById("chartMonthlyTrend"), {
      type: "bar",
      data: { labels, datasets: [{ label: "Total Bricks", data: bricks, backgroundColor: CHART_COLORS.brick }] },
      options: { responsive: true, plugins: { legend: { display: false } } },
    });
  } catch (e) { showMessage(msgEl, e.message, true); }
}

// -------------------- Profit Trend (line) --------------------
async function loadProfitTrendChart() {
  try {
    const d = await apiFetch("/admin/dashboard/monthly-profit-trend?months=6");
    const labels = d.months.map((r) => r.month);
    const profit = d.months.map((r) => r.profit);
    dashboardCharts.profit = new Chart(document.getElementById("chartProfitTrend"), {
      type: "line",
      data: { labels, datasets: [{
        label: "Net Profit (Rs.)", data: profit,
        borderColor: CHART_COLORS.ok,
        segment: { borderColor: (ctx) => (ctx.p0.parsed.y < 0 || ctx.p1.parsed.y < 0) ? CHART_COLORS.bad : CHART_COLORS.ok },
        tension: 0.2,
      }] },
      options: { responsive: true, plugins: { legend: { display: false } } },
    });
  } catch (e) { showMessage(msgEl, e.message, true); }
}

// -------------------- Cost Breakdown (pie) --------------------
async function loadCostBreakdownChart() {
  try {
    const d = await apiFetch("/admin/dashboard/cost-breakdown");
    dashboardCharts.costBreakdown = new Chart(document.getElementById("chartCostBreakdown"), {
      type: "doughnut",
      data: {
        labels: ["Raw Materials", "Making Charges", "Overhead"],
        datasets: [{
          data: [d.material_cost_per_brick, d.making_charge_per_brick, d.overhead_per_brick],
          backgroundColor: [CHART_COLORS.brick, CHART_COLORS.clay, CHART_COLORS.muted],
        }],
      },
      options: { responsive: true, plugins: { legend: { position: "bottom" } } },
    });
  } catch (e) { showMessage(msgEl, e.message, true); }
}

// -------------------- Stock Runway (bar) --------------------
async function loadStockRunwayChart() {
  try {
    const d = await apiFetch("/stock-overview");
    const labels = d.materials.map((m) => m.material);
    const days = d.materials.map((m) => m.days_left);
    dashboardCharts.stockRunway = new Chart(document.getElementById("chartStockRunway"), {
      type: "bar",
      data: { labels, datasets: [{
        label: "Days Left", data: days,
        backgroundColor: days.map((v) => (v < 7 ? CHART_COLORS.bad : v < 21 ? "#d99a2b" : CHART_COLORS.ok)),
      }] },
      options: { responsive: true, indexAxis: "y", plugins: { legend: { display: false } } },
    });
  } catch (e) { showMessage(msgEl, e.message, true); }
}

// -------------------- Sales Trend (line) --------------------
async function loadSalesTrendChart() {
  try {
    const d = await apiFetch("/admin/dashboard/sales-trend?days=30");
    const labels = d.days.map((r) => r.date.slice(5));
    const bricks = d.days.map((r) => r.bricks_sold);
    dashboardCharts.salesTrend = new Chart(document.getElementById("chartSalesTrend"), {
      type: "line",
      data: { labels, datasets: [{ label: "Bricks Sold", data: bricks, borderColor: CHART_COLORS.ok, tension: 0.25 }] },
      options: { responsive: true, plugins: { legend: { display: false } } },
    });
  } catch (e) { showMessage(msgEl, e.message, true); }
}

// -------------------- Top Customers (table) --------------------
async function loadTopCustomers() {
  try {
    const d = await apiFetch("/admin/dashboard/top-customers?limit=5");
    const tbody = document.querySelector("#topCustomersTable tbody");
    tbody.innerHTML = "";
    d.customers.forEach((c) => {
      textRow(tbody, [c.customer_name, c.customer_mobile, c.total_bricks, c.total_orders]);
    });
  } catch (e) { showMessage(msgEl, e.message, true); }
}

setInterval(() => {
  const dashboard = document.getElementById("sec-dashboard");
  if (!document.hidden && dashboard && !dashboard.classList.contains("hidden")) loadTodayActivity(false);
}, 60000);
