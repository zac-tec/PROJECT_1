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
    loadMonthMaterials(),
    loadDailyProductionChart(),
    loadMonthlyTrendChart(),
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
async function loadTodayActivity(markSeen = true, selectedDate = null) {
  try {
    const d = await apiFetch(selectedDate ? "/admin/dashboard/activity?date="+encodeURIComponent(selectedDate) : "/admin/dashboard/today-activity");
    const out = document.getElementById(selectedDate ? "datedActivityOutput" : "todayActivityOutput");

    let sections = [`<p><strong>${displayDate(d.date)}</strong></p>`];

    // Production
    if (d.production) {
      const p = d.production;
      sections.push(`
        <h2 style="margin-top:16px;">🏭 Production</h2>
        ${kvTable([
          { label: "Saved At", value: p.timestamp ? formatTime12(p.timestamp) : "Not recorded" },
          { label: "Mixes", value: p.mixes },
          {label:"Average bricks per mix",value:p.avg_bricks_per_mix ?? "N/A"},
          {label:"Labour cost per brick",value:p.labour_cost_per_brick===null?"N/A":`₹${p.labour_cost_per_brick.toFixed(4)}`},
          { label: "Bricks Produced", value: p.bricks_produced, bold: true },
          { label: "Labourers", value: p.labourers ?? "Not recorded" },
          {label:"Working hours",value:p.labour_hours ?? "Not recorded"},
          {label:"Labour cost (₹81.25/hour)",value:p.labour_cost===null?"Hours needed":money(p.labour_cost)},
          { label: "Misc Expense", value: p.misc_amount===null?"Not recorded":`${money(p.misc_amount)} (${p.misc_note || "—"})` },
        ])}
        ${p.is_corrected === "yes" ? '<p style="color:var(--muted);"><em>Corrected today.</em></p>' : ""}
      `);
    } else {
      sections.push(`<h2 style="margin-top:16px;">🏭 Production</h2><p style="color:var(--muted);">No production entry recorded for this date.</p>`);
    }

    // Sales
    if (d.sales.count > 0) {
      sections.push(`
        <h2 style="margin-top:16px;">🧱 Brick Sales</h2>
        ${kvTable([
          { label: "Sales Made", value: d.sales.count },
          { label: "Bricks Sold", value: d.sales.total_bricks },
          { label: "Revenue Billed", value: d.sales.total_revenue===null?"Not recorded":money(d.sales.total_revenue) },
          { label: "Amount Collected", value: d.sales.total_paid===null?"Not recorded":money(d.sales.total_paid), bold: true },
        ])}
      `);
    } else {
      sections.push(`<h2 style="margin-top:16px;">🧱 Brick Sales</h2><p style="color:var(--muted);">No sales recorded for this date.</p>`);
    }

    if(d.sale_entries?.length){
      const rows=d.sale_entries.map(r=>`<tr><td>${textHTML(r.time?formatTime12(r.time):'—')}</td><td>${textHTML(r.customer||'Not recorded')}</td><td>${textHTML(r.phone||'—')}</td><td>${r.bricks}</td><td>${r.price===null?'Not recorded':money(r.price)}</td><td>${r.amount===null?'Not recorded':money(r.amount)}</td></tr>`).join('');
      sections.push(`<div class="table-scroll"><table><thead><tr><th>Time</th><th>Customer</th><th>Phone</th><th>Bricks</th><th>Price</th><th>Amount</th></tr></thead><tbody>${rows}</tbody></table></div>`);
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
        : event.type === 'material_stock_estimate' ? `${formatTime12(event.time)} · ${detail.material}: stock corrected to ${detail.new_stock}.`
        : `${formatTime12(event.time)} · ${event.actor} ${detail.previous_amount === null ? "saved" : "updated"} ${detail.bill_type} for ${detail.month}: ${money(detail.amount)}${detail.previous_amount === null ? "" : ` (previously ${money(detail.previous_amount)})`}.`;
      out.append(line);
    }
    if (!(d.updated_bills || []).length && !(d.operational_events || []).length) {
      const empty = document.createElement("p");
      empty.textContent = "No bills or material receipts recorded for this date.";
      out.append(empty);
    }

    // Mark today's activity as "seen" now that the admin has actually
    // opened the Dashboard — clears the sidebar badge.
    if (!selectedDate && markSeen) localStorage.setItem(`activitySeen-${d.date}`, String(d.activity_count));
    if(!selectedDate)updateDashboardBadge(d.activity_count, d.date);
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
    document.getElementById("fact-pending").style.color = d.pending_customer_dues>0 ? "#b42318" : "#15753b";
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
    const labels = d.days.map((r) => displayDate(r.date)); // MM-DD
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
    const labels = d.days.map((r) => displayDate(r.date));
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

async function loadMonthMaterials(){
 const out=document.getElementById('monthMaterialsOutput');
 try{
  const input=document.getElementById('materialReportMonth');
  if(!input.value)input.value=new Date().toLocaleDateString('sv-SE',{timeZone:'Asia/Kolkata'}).slice(0,7);
  const d=await apiFetch('/admin/dashboard/month-materials?month='+input.value);
  const sales=await apiFetch('/brick-sales/monthly-summary?month='+input.value);
  document.getElementById('monthSalesOverview').innerHTML=kvTable([{label:'Month',value:input.value},{label:'Total bricks sold',value:sales.total_bricks_sold},{label:'Historical sales quantities',value:sales.historical_bricks},{label:'New invoice quantities',value:sales.recorded_bricks},{label:'Historical unit price',value:sales.historical_unit_price===null?'Not set':money(sales.historical_unit_price)+' (including '+sales.historical_gst_rate+'% GST)'},{label:'Sales revenue excluding GST',value:sales.total_revenue===null?'Price needed':money(sales.total_revenue)}]);
  out.innerHTML=kvTable([{label:'Month',value:d.month},{label:'Bricks produced',value:d.bricks},{label:'Mixes',value:d.mixes},
   ...Object.entries(d.materials).map(([k,v])=>({label:k+' consumed',value:['Sand','Flyash'].includes(k)?`${Number((v/1000).toFixed(3))} tonnes (${v} kg)`:`${v} ${k==='Chemical'?'L':'bags'}`})),
   {label:'Material cost',value:money(d.material_cost)},{label:'Making charges subtotal — recorded costs',value:money(d.making_cost)},
   {label:'Loading',value:money(d.loading_cost)},{label:'Union',value:money(d.union_cost)},
   {label:'Recorded working hours',value:d.recorded_labour_hours},
   {label:'Labour cost — recorded hours',value:money(d.recorded_labour_cost)},
   {label:'Average labour / brick (days with hours)',value:d.average_labour_per_brick===null?'Hours needed':money(d.average_labour_per_brick)},
   {label:'Production days without recorded hours',value:d.labour_missing_days},
   {label:'Recorded miscellaneous expenses',value:money(d.misc_expenses)},{label:'Full-month fixed / utility charges',value:money(d.overhead.total_overhead)},
   {label:d.historical_days?'Estimated total cost':'Total cost',value:d.total_cost===null?'Pending missing working hours / costs':money(d.total_cost)}]);
  if(dashboardCharts.monthActual)dashboardCharts.monthActual.destroy();
  dashboardCharts.monthActual=new Chart(document.getElementById('chartMonthActual'),{type:'bar',data:{labels:d.days.map(r=>displayDate(r.production_date)),datasets:[{label:'Bricks produced',data:d.days.map(r=>r.bricks_made),backgroundColor:CHART_COLORS.brick}]},options:{responsive:true}});
 }catch(e){out.textContent=e.message;}
}

function loadSelectedActivity(){
 const input=document.getElementById('activityDate');
 if(!input.value)return;
 return loadTodayActivity(false,input.value);
}
onSectionLoad('activity',()=>{
 const input=document.getElementById('activityDate');
 input.max=new Date().toLocaleDateString('sv-SE',{timeZone:'Asia/Kolkata'});
 if(!input.value)input.value=input.max;
 return loadSelectedActivity();
});
