requireRole("admin");
document.getElementById("whoami").textContent = `${sessionStorage.getItem("username")} (admin)`;

const msgEl = document.getElementById("msg");
const STOCK_UNITS = { Flyash: "kg", Sand: "kg", Chemical: "L", Cement: "packets" };

// -------------------- Rate Management (inline edit) --------------------
async function loadRates() {
  const rates = await apiFetch("/rates");
  const rows = Object.entries(rates).map(([material, rate]) => ({
    key: material,
    label: rate.scheduled_rate === null
      ? material
      : `${material} · ${money(rate.scheduled_rate)} from ${rate.effective_from}`,
    rawValue: rate.current_rate,
  }));
  renderInlineEditTable(
    document.querySelector("#ratesTable tbody"),
    rows,
    async (key, newValue) => {
      const r = await apiFetch(`/rates/${key}`, { method: "PUT", body: { new_rate: newValue } });
      showMessage(msgEl, `${key}: ${money(r.new_rate)} applies from ${r.effective_from}. Today's material costs have been updated; earlier days are unchanged.`);
      sessionUI.discard([`inline-ratesTable-${key}`]);
      await sessionUI.afterSave(loadRates);
      await sessionUI.afterSave(loadRateHistory);
    },
    (v) => money(v)
  );
}

async function loadRateHistory() {
  const data = await apiFetch("/rates/history");
  const tbody = document.querySelector("#rateHistoryTable tbody");
  tbody.innerHTML = "";
  (data.history || []).slice().reverse().forEach((h) => {
    const tr = document.createElement("tr");
    for (const value of [
      `${h.timestamp.split(" ")[0]} ${formatTime12(h.timestamp.split(" ")[1])}`,
      h.material, money(h.old_rate), money(h.new_rate), h.effective_from || "—",
    ]) { const td = document.createElement("td"); td.textContent = value; tr.append(td); }
    tbody.append(tr);
  });
}

// -------------------- Making Charges (inline edit) --------------------
async function loadCharges() {
  const data = await apiFetch("/charges");
  const rows = Object.entries(data.charges).map(([name, value]) => ({ key: name, label: name, rawValue: value }));
  renderInlineEditTable(
    document.querySelector("#chargesTable tbody"),
    rows,
    async (key, newValue) => {
      const r = await apiFetch(`/charges/${key}`, { method: "PUT", body: { new_value: newValue } });
      showMessage(msgEl, `${key} updated: ${money(r.old_value)} → ${money(r.new_value)}`);
      sessionUI.discard([`inline-chargesTable-${key}`]);
      await sessionUI.afterSave(loadCharges);
      await sessionUI.afterSave(loadChargeHistory);
    },
    (v) => money(v)
  );
  document.getElementById("chargesTotal").textContent = money(data.total_making_charge);
}

async function loadChargeHistory() {
  const data = await apiFetch("/charges/history");
  const tbody = document.querySelector("#chargeHistoryTable tbody");
  tbody.innerHTML = "";
  (data.history || []).slice().reverse().forEach((h) => {
    tbody.innerHTML += `<tr><td>${h.timestamp.split(" ")[0]} ${formatTime12(h.timestamp.split(" ")[1])}</td><td>${h.charge_name}</td><td>${money(h.old_value)}</td><td>${money(h.new_value)}</td></tr>`;
  });
}

// -------------------- Fixed Monthly Charges (inline edit) --------------------
async function loadFixedCharges() {
  const data = await apiFetch("/fixed-monthly-charges");
  const rows = Object.entries(data).map(([key, info]) => ({ key, label: info.label, rawValue: info.value }));
  renderInlineEditTable(
    document.querySelector("#fixedChargesTable tbody"),
    rows,
    async (key, newValue) => {
      const r = await apiFetch(`/fixed-monthly-charges/${key}`, { method: "PUT", body: { new_value: newValue } });
      showMessage(msgEl, `${r.label} updated: ${money(r.old_value)} → ${money(r.new_value)}`);
      sessionUI.discard([`inline-fixedChargesTable-${key}`]);
      await sessionUI.afterSave(loadFixedCharges);
    },
    (v) => money(v)
  );
}

// -------------------- Recipe Management (inline edit) --------------------
async function loadRecipe() {
  const data = await apiFetch("/recipe");
  const rows = Object.entries(data).map(([material, info]) => ({
    key: material, label: `${material} (${info.unit})`, rawValue: info.qty_per_mix,
  }));
  renderInlineEditTable(
    document.querySelector("#recipeTable tbody"),
    rows,
    async (key, newValue) => {
      const r = await apiFetch(`/recipe/${key}`, { method: "PUT", body: { new_qty_per_mix: newValue } });
      showMessage(msgEl, `${key} recipe updated: ${r.old_qty_per_mix} → ${r.new_qty_per_mix}`);
      sessionUI.discard([`inline-recipeTable-${key}`]);
      await sessionUI.afterSave(loadRecipe);
    },
    (v) => v,
    "0.001"
  );
}

// -------------------- Default Brick Sale Price (inline edit) --------------------
async function loadProductionCosts() {
  try {
    const month = document.getElementById("costMonth").value;
    const d = await apiFetch("/reports/production-costs" + (month ? "?month="+month : ""));
    const oh = d.overhead;
    const rows = [
      {label:"Month",value:d.month}, {label:"Days recorded",value:d.days_worked},
      {label:"Bricks produced",value:d.bricks,bold:true}, {label:"Mixes run",value:d.mixes},
      {label:"Average bricks per mix",value:d.average_bricks_per_mix ?? "—"},
      {label:"Materials used",value:money(d.material_cost)},
      {label:"Making charges subtotal — recorded costs",value:money(d.making_cost)},
      {label:"Loading",value:money(d.loading_cost)},{label:"Union",value:money(d.union_cost)},
      {label:"Recorded working hours",value:d.recorded_labour_hours},
      {label:"Labour cost — recorded hours",value:money(d.recorded_labour_cost)},
      {label:"Average labour / brick (days with hours)",value:d.average_labour_per_brick===null?"Hours needed":money(d.average_labour_per_brick)},
      {label:"Days without working hours",value:d.labour_missing_days},
      {label:"Miscellaneous expenses",value:money(d.misc_expenses)},
      {label:"Rent",value:money(oh.rent)}, {label:"Manager salary",value:money(oh.manager_salary)},
      {label:"Electricity ("+(oh.electricity_is_default ? "estimate" : "saved bill")+")",value:money(oh.electricity)},
      {label:"Water ("+(oh.water_is_default ? "estimate" : "saved bill")+")",value:money(oh.water)},
      {label:"Total production and monthly cost",value:d.total_cost === null ? "Unavailable" : money(d.total_cost),bold:true},
      {label:"Cost per brick produced",value:d.cost_per_brick === null ? "Unavailable — no production or missing costs" : money(d.cost_per_brick),bold:true}
    ];
    const output = document.getElementById("productionCostsOutput");
    output.innerHTML = kvTable(rows);
    const note = document.createElement("p");
    note.textContent = "Cost per brick = (materials + making charges + miscellaneous + monthly overhead) ÷ bricks produced. Estimates change when actual bills are entered." +
      (d.historical_days ? " Material consumption uses the saved recipe. Unrecorded miscellaneous expenses are excluded." : "") +
      (d.baseline_days ? " "+d.baseline_days+" older day(s) use estimated costs captured at migration; original historical rates were not saved." : "");
    output.append(note);
    const table = document.createElement("table");
    table.innerHTML = "<thead><tr><th>Date</th><th>Mixes</th><th>Bricks</th><th>Working hours / cost</th><th>Misc.</th><th>Note</th><th>Cost basis</th></tr></thead><tbody></tbody>";
    for(const day of d.days) {
      const tr=document.createElement("tr");
      for(const value of [day.production_date,day.mixes_run,day.bricks_made,day.labour_hours==null?"Hours not recorded":`${day.labour_hours} h / ${money(day.labour_cost_total)}`,money(day.misc_expense),day.misc_note,day.snapshot_source==="recorded" ? "Saved rates" : day.snapshot_source==="historical_estimate" ? "Imported record" : "Migration estimate"]) {
        const td=document.createElement("td"); td.textContent=value; tr.append(td);
      }
      table.querySelector("tbody").append(tr);
    }
    const scroll=document.createElement("div"); scroll.className="table-scroll"; scroll.append(table); output.append(scroll);
  } catch(e) { showMessage(msgEl,e.message,true); }
}

// -------------------- Stock Overview / Max Producible --------------------
async function loadStockOverview() {
  try {
    const d = await apiFetch("/stock-overview");
    let rows = d.materials.map((m) => `<tr><td>${m.material}</td><td>${["Flyash", "Sand"].includes(m.material) ? `${Number((m.stock_qty / 1000).toFixed(3))} tonnes (${m.stock_qty} kg)` : `${m.stock_qty} ${STOCK_UNITS[m.material] || ""}`}</td><td>${m.qty_per_mix}</td><td>${m.days_left} days</td><td>${money(m.unit_rate)}</td><td>${money(m.asset_value)}</td></tr>`).join("");
    const summaryTable = kvTable([
      { label: "Run-rate", value: `${d.avg_daily_mixes} mixes/day` },
      { label: "Total Capital Locked", value: money(d.total_capital_value), bold: true },
      { label: `Bottleneck: ${d.bottleneck_material}`, value: `~${d.critical_days} days left`, color: "var(--bad)", bold: true },
    ]);
    document.getElementById("stockOverviewOutput").innerHTML = `
      <table><thead><tr><th>Material</th><th>Stock</th><th>Recipe/Mix</th><th>Days Left</th><th>Rate</th><th>Asset Value</th></tr></thead><tbody>${rows}</tbody></table>
      <h2 style="margin-top:20px;">Summary</h2>
      ${summaryTable}`;
  } catch (e) { showMessage(msgEl, e.message, true); }
}

async function loadMaxProducible() {
  try {
    const d = await apiFetch("/max-producible");
    let rows = Object.entries(d.possible_mixes_per_material).map(([m, v]) => `<tr><td>${m}</td><td>${v}</td></tr>`).join("");
    const summaryTable = kvTable([
      { label: `Bottleneck: ${d.bottleneck_material}`, value: `${d.max_mixes_possible} mix(es)`, color: "var(--bad)" },
      { label: "Max Bricks Producible Now", value: d.max_bricks_possible.toLocaleString("en-IN"), bold: true, color: "var(--ok)" },
    ]);
    document.getElementById("maxProducibleOutput").innerHTML = `
      <table><thead><tr><th>Material</th><th>Possible Whole Mixes</th></tr></thead><tbody>${rows}</tbody></table>
      <h2 style="margin-top:20px;">Summary</h2>
      ${summaryTable}`;
  } catch (e) { showMessage(msgEl, e.message, true); }
}

// -------------------- Profit Calculator --------------------
async function loadOverheadDefaultsForProfit() {
  const month = document.getElementById("profitMonth").value.trim() || null;
  try {
    const d = await apiFetch(`/reports/overhead${month ? `?month=${month}` : ""}`);
    const sales = await apiFetch('/brick-sales/monthly-summary' + (month ? '?month=' + month : ''));
    document.getElementById('profitSellingPrice').value = sales.historical_unit_price ?? '';
    document.getElementById('profitOutput').textContent = sales.historical_unit_price !== null ? `Confirmed historical price: ${money(sales.historical_unit_price)}/brick including ${sales.historical_gst_rate}% GST; base ${money(sales.historical_base_price)}. Press Calculate.` : 'Enter a price for unpriced sales and press Calculate.';
    sessionUI.savedValue("profitRentOverride", d.rent);
    sessionUI.savedValue("profitSalaryOverride", d.manager_salary);
    sessionUI.savedValue("profitElectricityOverride", d.electricity);
    sessionUI.savedValue("profitWaterOverride", d.water);
    document.getElementById("profitElectricitySourceTag").textContent =
      d.electricity_is_default ? "(default)" : "(actual bill)";
    document.getElementById("profitWaterSourceTag").textContent =
      d.water_is_default ? "(default)" : "(actual bill)";
  } catch (e) { showMessage(msgEl, e.message, true); }
}

async function runProfitCalculator() {
 const out=document.getElementById('profitOutput');out.replaceChildren();
 const price=Number(document.getElementById('profitSellingPrice').value);
 if(!Number.isFinite(price)||price<=0){out.textContent='Enter the price for unpriced sales to calculate revenue and estimated profit.';return;}
 const month=document.getElementById('profitMonth').value||null;
 const raw=document.getElementById('profitBricksSold').value.trim();
 const body={month,selling_price:price,bricks_sold:raw===''?null:Number(raw)};
 for(const [key,id] of [['rent_override','profitRentOverride'],['manager_salary_override','profitSalaryOverride'],['electricity_default_override','profitElectricityOverride'],['water_default_override','profitWaterOverride']]){
  const v=document.getElementById(id).value.trim();body[key]=v===''?null:Number(v);
 }
 try{
  const d=await apiFetch('/profit-calculator',{method:'POST',body});
  const amount=v=>v===null?'Pending working hours / cost records':money(v);
  out.innerHTML=kvTable([{label:'Month',value:d.month},{label:d.scenario?'Scenario bricks sold':'Recorded bricks sold',value:d.bricks_sold},
   {label:'Historical bricks sold',value:d.historical_bricks},{label:'New invoice bricks sold',value:d.recorded_bricks},
   {label:'Historical sales revenue (excluding GST)',value:money(d.historical_revenue_estimate)},
   {label:'New invoice revenue (excluding GST)',value:money(d.recorded_revenue)},
   {label:d.scenario?'Scenario revenue':'Combined revenue (excluding GST)',value:money(d.gross_revenue)},
   {label:'Estimated cost of sold bricks',value:amount(d.estimated_cost_of_sales)},
   {label:'Full-month fixed / utility charges',value:money(d.overhead.total_overhead)},
   {label:'Recorded miscellaneous expenses',value:money(d.misc_expenses)},
   {label:d.net_profit===null?'Estimated profit / loss':d.net_profit<0?'Estimated loss':d.net_profit>0?'Estimated profit':'Break-even',value:d.net_profit===null?amount(null):money(Math.abs(d.net_profit)),bold:true}]);
  const resultRow=out.querySelector('tr:last-child');if(resultRow && d.net_profit!==null)resultRow.classList.add(d.net_profit<0?'financial-negative':'financial-positive');
  const note=document.createElement('p');note.textContent=d.note;out.append(note);
 }catch(e){out.textContent=e.message;}
}

// -------------------- Order Planning --------------------
async function runOrderCalculation() {
  const orderBricks = parseInt(document.getElementById("orderBricks").value, 10);
  if (!orderBricks || orderBricks <= 0) return showMessage(msgEl, "Enter a valid order size.", true);
  try {
    const d = await apiFetch("/order-planning", { method: "POST", body: { order_bricks: orderBricks } });
    let rows = d.materials.map((m) => `<tr><td>${m.material}</td><td>${m.needed} ${STOCK_UNITS[m.material] || ""}</td><td>${m.in_stock} ${STOCK_UNITS[m.material] || ""}</td><td style="color:${m.sufficient ? 'var(--ok)' : 'var(--bad)'};">${m.sufficient ? "sufficient" : m.deficit}</td></tr>`).join("");
    const noteLine = d.note ? `<p style="color:var(--muted);">ℹ️ ${textHTML(d.note)}</p>` : "";
    const summaryTable = kvTable([
      { label: "Order Size", value: `${d.order_bricks} bricks` },
      { label: "Exact Mixes Needed", value: d.exact_mixes_needed },
      { label: "Whole Mixes Needed", value: d.whole_mixes_needed, bold: true },
    ]);
    document.getElementById("orderOutput").innerHTML = `
      ${summaryTable}
      ${noteLine}
      <h2 style="margin-top:20px;">Materials Required</h2>
      <table><thead><tr><th>Material</th><th>Needed</th><th>In Stock</th><th>Deficit</th></tr></thead><tbody>${rows}</tbody></table>`;
  } catch (e) { showMessage(msgEl, e.message, true); }
}

// -------------------- Brick Sales (Admin View) --------------------
async function loadAdminOutletStock() {
  const d = await apiFetch("/brick-sales/outlet-stock");
  document.getElementById("adminOutletStockValue").textContent = d.total_bricks.toLocaleString("en-IN");
  document.getElementById("adminCuringStockValue").textContent = d.curing.toLocaleString("en-IN");
  document.getElementById("adminEarlySaleStockValue").textContent = d.early_sale.toLocaleString("en-IN");
  document.getElementById("adminFullyCuredStockValue").textContent = d.fully_cured.toLocaleString("en-IN");
  document.getElementById("adminSaleableStockValue").textContent = d.saleable.toLocaleString("en-IN");
  const tbody = document.querySelector("#adminBrickBatchesTable tbody");
  tbody.replaceChildren();
  for (const batch of d.batches) {
    const row = document.createElement("tr");
    const source = batch.source === "opening" ? "Opening stock" : batch.source === "production" ? `Production #${batch.batch_id}` : batch.source === "return" ? `Return #${batch.batch_id}` : `Transfer #${batch.batch_id}`;
    const status = batch.stage === "curing" ? "Curing" : batch.stage === "early_sale" ? "Early-sale eligible" : "Fully cured";
    const values = [source, batch.production_date || batch.received_date, batch.age_days === null ? "Received cured" : `${batch.age_days} days`, status, Number(batch.remaining_quantity).toLocaleString("en-IN")];
    for (const value of values) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    }
    tbody.append(row);
  }
}

async function loadMonthlySalesSummary() {
  const month = document.getElementById("salesSummaryMonth").value.trim();
  try {
    const d = await apiFetch(`/brick-sales/monthly-summary${month ? `?month=${month}` : ""}`);
    document.getElementById("salesSummaryOutput").innerHTML = kvTable([
      { label: "Month", value: d.month },
      { label: "Total Bricks Sold", value: d.total_bricks_sold.toLocaleString("en-IN"), bold: true },
      { label: "Total Sales Transactions", value: d.total_sales_count },
      { label: "Sales revenue (excluding GST)", value: d.total_revenue === null ? "Price required — use Profit Calculator" : money(d.total_revenue) },
      { label: "GST on new invoices", value: money(d.recorded_gst) },
      { label: "Historical GST", value: d.historical_gst===null ? 'Not recorded' : money(d.historical_gst) },
      { label: "Collected on new invoices (older payment details unavailable)", value: money(d.total_collected), bold: true },
    ]);
  } catch (e) { showMessage(msgEl, e.message, true); }
}

async function loadAllBrickSales() {
  try {
    const d = await apiFetch("/brick-sales");
    const tbody = document.querySelector("#allSalesTable tbody");
  tbody.replaceChildren();
  for (const s of d.sales) {
    textRow(tbody, [s.date, formatTime12(s.time), s.customer_name + (s.is_edited === "yes" ? " (edited)" : ""), s.customer_mobile, s.bricks_purchased, money(s.total_amount), money(s.amount_paid), Math.max(0,s.total_amount-s.amount_paid)>0 ? "Outstanding: " + money(s.total_amount-s.amount_paid) : "Fully paid"],
      [["Print Receipt", "printer", () => openReceipt(s.sale_id)]]);
    const row=tbody.lastElementChild;
    row.children[7].classList.add(s.amount_paid>=s.total_amount ? 'financial-positive' : 'financial-negative');
    if(s.amount_paid<s.total_amount){
      const button=document.createElement('button');button.textContent='Mark paid';
      button.addEventListener('click',async()=>{
        if(!await confirmAction(`Confirm receipt of the remaining ${money(s.total_amount-s.amount_paid)} from ${s.customer_name}?`))return;
        try{
          await apiFetch(`/admin/sales/${s.sale_id}/mark-paid`,{method:'POST',body:{expected_total:s.total_amount,expected_paid:s.amount_paid}});
          await loadAllBrickSales();await loadMonthlySalesSummary();
        }catch(e){showMessage(msgEl,e.message,true);}
      });row.lastElementChild.append(button);
    }
  }
  refreshIcons();
  } catch (e) { showMessage(msgEl, e.message, true); }
}

// Opens the PDF receipt in a new tab — user can view, print, or save from there.
function openReceipt(saleId) {
  return openPDF(`/manager/sales/${saleId}/receipt`, `receipt_${saleId}.pdf`);
}

// -------------------- Customer Lookup --------------------
let _customerSearchTimeout = null;

function searchCustomers() {
  clearTimeout(_customerSearchTimeout);
  const q = document.getElementById("customerSearchInput").value.trim();
  const resultsEl = document.getElementById("customerSearchResults");
  document.getElementById("customerHistoryOutput").innerHTML = "";

  if (q.length < 2) {
    resultsEl.innerHTML = "";
    return;
  }

  _customerSearchTimeout = setTimeout(async () => {
    try {
      const d = await apiFetch(`/manager/sales/customers/search?q=${encodeURIComponent(q)}`);
      if (d.customers.length === 0) {
        resultsEl.innerHTML = `<p style="color:var(--muted);">No customers found.</p>`;
        return;
      }
      customerResults(resultsEl, d.customers);
    } catch (e) { showMessage(msgEl, e.message, true); }
  }, 300);
}

async function showCustomerHistory(mobile) {
  try {
    const d = await apiFetch(`/manager/sales/customers/${encodeURIComponent(mobile)}/history`);
    const summary = kvTable([
      { label: "Customer", value: d.customer_name, bold: true },
      { label: "Total Orders", value: d.total_orders },
      { label: "Total Bricks Purchased", value: d.total_bricks },
      { label: "Total Billed", value: money(d.total_billed) },
      { label: "Total Paid", value: money(d.total_paid) },
      { label: "Pending Dues", value: money(d.pending_dues), bold: true, color: d.pending_dues > 0 ? "var(--bad)" : "var(--ok)" },
    ]);
    customerOrders(document.getElementById("customerHistoryOutput"), summary, d.orders);
    refreshIcons();
  } catch (e) { showMessage(msgEl, e.message, true); }
}

// -------------------- Delivery Settings (WhatsApp, Email, Schedule) --------------------
async function loadDeliverySettings() {
  try {
    const d = await apiFetch("/daily-report/delivery-settings");
    sessionUI.savedValue("whatsappNumberInput", d.whatsapp_number || "");
    sessionUI.savedValue("clientEmailInput", d.email || "");
    sessionUI.savedValue("autoSendTimeInput", d.send_time || "20:00");
    sessionUI.savedValue("autoSendEnabledInput", d.auto_send_enabled);
  } catch (e) { showMessage(msgEl, e.message, true); }
}

async function updateWhatsappNumber() {
  const number = document.getElementById("whatsappNumberInput").value.trim();
  if (!number) return showMessage(msgEl, "Enter a WhatsApp number.", true);
  try {
    await apiFetch("/daily-report/whatsapp-number", { method: "PUT", body: { number } });
    sessionUI.discard(["whatsappNumberInput"]);
    showMessage(msgEl, "Client WhatsApp number saved.");
  } catch (e) { showMessage(msgEl, e.message, true); }
}

async function updateClientEmail() {
  const email = document.getElementById("clientEmailInput").value.trim();
  if (!email) return showMessage(msgEl, "Enter an email address.", true);
  try {
    await apiFetch("/daily-report/email", { method: "PUT", body: { email } });
    sessionUI.discard(["clientEmailInput"]);
    showMessage(msgEl, "Client email saved.");
  } catch (e) { showMessage(msgEl, e.message, true); }
}

async function updateSchedule() {
  const send_time = document.getElementById("autoSendTimeInput").value || "20:00";
  const enabled = document.getElementById("autoSendEnabledInput").checked;
  try {
    await apiFetch("/daily-report/schedule", { method: "PUT", body: { send_time, enabled } });
    sessionUI.discard(["autoSendTimeInput", "autoSendEnabledInput"]);
    showMessage(msgEl, enabled
      ? `Auto-email turned ON — will send daily at ${send_time}.`
      : "Auto-email turned OFF.");
  } catch (e) { showMessage(msgEl, e.message, true); }
}

async function sendEmailNow() {
  try {
    const d = await apiFetch("/daily-report/send-email-now", { method: "POST" });
    showMessage(msgEl, d.message);
  } catch (e) { showMessage(msgEl, e.message, true); }
}

onSectionLoad("dashboard", markSeen => loadDashboard(markSeen));
onSectionLoad("reportsettings", loadDeliverySettings);
onSectionLoad("pricing", () => Promise.all([loadRates(), loadCharges(), loadFixedCharges(), loadRecipe()]));
onSectionLoad("history", () => Promise.all([loadRateHistory(), loadChargeHistory()]));
onSectionLoad("productionCosts", loadProductionCosts);
onSectionLoad("stock", () => Promise.all([loadStockOverview(), loadMaxProducible()]));
onSectionLoad("profit", async () => { await loadOverheadDefaultsForProfit(); });
onSectionLoad("orders", loadFunFacts);
onSectionLoad("brickSales", () => Promise.all([loadAdminOutletStock(), loadMonthlySalesSummary(), loadAllBrickSales()]));

(async function init() {
  try {
    refreshIcons();
    await initSectionNav("dashboard");

  } catch (e) { showMessage(msgEl, e.message, true); }
})();
