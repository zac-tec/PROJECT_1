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
      showMessage(msgEl, `${key}: ${money(r.new_rate)} scheduled from ${r.effective_from}. Today's rate remains ${money(r.current_rate)}.`);
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
async function loadDefaultBrickPrice() {
  const d = await apiFetch("/default-brick-price");
  const rows = [{ key: "default_cost_per_brick", label: "Default Cost Per Brick", rawValue: d.default_cost_per_brick }];
  renderInlineEditTable(
    document.getElementById("salePriceTableBody"),
    rows,
    async (key, newValue) => {
      const r = await apiFetch("/default-brick-price", { method: "PUT", body: { new_value: newValue } });
      showMessage(msgEl, `Default price updated: ${money(r.old_value)} → ${money(r.new_value)}`);
      sessionUI.discard([`inline-salePriceTableBody-${key}`]);
      await sessionUI.afterSave(loadDefaultBrickPrice);
    },
    (v) => money(v)
  );
}

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
      {label:"Making charges",value:money(d.making_cost)},
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
      (d.baseline_days ? " "+d.baseline_days+" older day(s) use estimated costs captured at migration; original historical rates were not saved." : "");
    output.append(note);
    const table = document.createElement("table");
    table.innerHTML = "<thead><tr><th>Date</th><th>Mixes</th><th>Bricks</th><th>Labour</th><th>Misc.</th><th>Note</th><th>Cost basis</th></tr></thead><tbody></tbody>";
    for(const day of d.days) {
      const tr=document.createElement("tr");
      for(const value of [day.production_date,day.mixes_run,day.bricks_made,day.labourers_present,money(day.misc_expense),day.misc_note,day.snapshot_source==="recorded" ? "Saved rates" : "Migration estimate"]) {
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
    let rows = d.materials.map((m) => `<tr><td>${m.material}</td><td>${m.stock_qty} ${STOCK_UNITS[m.material] || ""}</td><td>${m.qty_per_mix}</td><td>${m.days_left} days</td><td>${money(m.unit_rate)}</td><td>${money(m.asset_value)}</td></tr>`).join("");
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
  const month = document.getElementById("profitMonth").value.trim() || null;
  const sellingPriceRaw = document.getElementById("profitSellingPrice").value.trim();
  const sellingPrice = sellingPriceRaw === "" ? null : parseFloat(sellingPriceRaw);
  const bricksSoldRaw = document.getElementById("profitBricksSold").value.trim();
  const bricksSold = bricksSoldRaw === "" ? null : parseInt(bricksSoldRaw, 10);

  const readOverride = (id) => {
    const raw = document.getElementById(id).value.trim();
    return raw === "" ? null : parseFloat(raw);
  };

  try {
    const d = await apiFetch("/profit-calculator", {
      method: "POST",
      body: {
        month,
        selling_price: sellingPrice,
        bricks_sold: bricksSold,
        rent_override: readOverride("profitRentOverride"),
        manager_salary_override: readOverride("profitSalaryOverride"),
        electricity_default_override: readOverride("profitElectricityOverride"),
        water_default_override: readOverride("profitWaterOverride"),
      },
    });

    const revenueTable = kvTable([
      { label: `Gross Revenue (${d.bricks_sold} sold @ ${money(d.selling_price)}${d.selling_price_was_defaulted ? ", default price" : ""})`, value: money(d.gross_revenue), bold: true },
    ]);

    let expenseRows;
    if (d.used_live_config_fallback) {
      expenseRows = [
        { label: "⚠️ No production entries this month — using live configuration", value: "" },
        { label: "Cost of Bricks Sold", value: money(d.cost_of_bricks_sold) },
        { label: "Base Cost Per Brick", value: money(d.base_cost_per_brick) },
      ];
    } else {
      expenseRows = [
        { label: "Raw Materials Cost", value: money(d.raw_materials_cost) },
        { label: "Material Cost Per Brick", value: money(d.material_cost_per_brick) },
        { label: "Fixed Making Charges", value: money(d.fixed_making_charges) },
        { label: "Making Charge Per Brick", value: money(d.making_charge_per_brick) },
      ];
    }
    const expenseTable = kvTable(expenseRows);

    const oh = d.overhead;
    const overheadTable = kvTable([
      { label: "Rent", value: money(oh.rent) },
      { label: "Manager Salary", value: money(oh.manager_salary) },
      { label: `Electricity${oh.electricity_is_default ? " (default)" : " (actual)"}`, value: money(oh.electricity) },
      { label: `Water${oh.water_is_default ? " (default)" : " (actual)"}`, value: money(oh.water) },
      { label: "Total Monthly Overhead", value: money(oh.total_overhead), bold: true },
    ]);

    const outcomeColor = d.is_profit ? "var(--ok)" : "var(--bad)";
    const outcomeTable = kvTable([
      { label: "Incidental Misc", value: money(d.total_misc_leakages) },
      { label: "Total Expenditures", value: money(d.total_expenditures), bold: true },
      { label: d.is_profit ? "Net Projected Profit" : "Net Financial Loss", value: money(d.net_profit), bold: true, color: outcomeColor },
      { label: "Return Margin", value: `${d.profit_margin_pct}%`, bold: true, color: outcomeColor },
    ]);

    document.getElementById("profitOutput").innerHTML = `
      ${revenueTable}
      <h2 style="margin-top:20px;">Cost Breakdown</h2>
      ${expenseTable}
      <h2 style="margin-top:20px;">Monthly Overhead</h2>
      ${overheadTable}
      <h2 style="margin-top:20px;">Outcome</h2>
      ${outcomeTable}`;
  } catch (e) { showMessage(msgEl, e.message, true); }
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
      { label: "Total Revenue (billed)", value: money(d.total_revenue) },
      { label: "Total Collected (actually paid)", value: money(d.total_collected), bold: true },
    ]);
  } catch (e) { showMessage(msgEl, e.message, true); }
}

async function loadAllBrickSales() {
  try {
    const d = await apiFetch("/brick-sales");
    const tbody = document.querySelector("#allSalesTable tbody");
  tbody.replaceChildren();
  for (const s of d.sales) {
    textRow(tbody, [s.date, formatTime12(s.time), s.customer_name + (s.is_edited === "yes" ? " (edited)" : ""), s.customer_mobile, s.bricks_purchased, money(s.total_amount), money(s.amount_paid)],
      [["Print Receipt", "printer", () => openReceipt(s.sale_id)]]);
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
onSectionLoad("rates", () => Promise.all([loadRates(), loadRateHistory()]));
onSectionLoad("charges", () => Promise.all([loadCharges(), loadChargeHistory()]));
onSectionLoad("history", () => Promise.all([loadRateHistory(), loadChargeHistory()]));
onSectionLoad("fixedcharges", loadFixedCharges);
onSectionLoad("recipe", loadRecipe);
onSectionLoad("saleprice", loadDefaultBrickPrice);
onSectionLoad("productionCosts", loadProductionCosts);
onSectionLoad("stock", () => Promise.all([loadStockOverview(), loadMaxProducible()]));
onSectionLoad("profit", async () => { await loadOverheadDefaultsForProfit(); await runProfitCalculator(); });
onSectionLoad("orders", loadFunFacts);
onSectionLoad("brickSales", () => Promise.all([loadAdminOutletStock(), loadMonthlySalesSummary(), loadAllBrickSales()]));

(async function init() {
  try {
    refreshIcons();
    await initSectionNav("dashboard");

  } catch (e) { showMessage(msgEl, e.message, true); }
})();
