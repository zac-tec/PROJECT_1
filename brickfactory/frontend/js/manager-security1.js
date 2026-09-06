requireRole("manager");
document.getElementById("whoami").textContent = `${sessionStorage.getItem("username")} (manager)`;

const msgEl = document.getElementById("msg");
let currentPreview = null; // holds {mixes, bricks_produced, calculated_field} between preview and save
let editingSaleId = null;   // null = creating a new sale, otherwise editing this sale_id

// -------------------- Today's Existing Entry --------------------
// GET /manager/production/today -> {exists: bool, ...}
async function checkExistingEntry() {
  const d = await apiFetch("/manager/production/today");
  const card = document.getElementById("existingEntryCard");
  if (!d.exists) {
    card.innerHTML = "<h2>Today's Saved Entry</h2><p style=\"color:var(--muted);\">No entry saved yet for today.</p>";
    return;
  }
  const table = kvTable([
    { label: "Saved At", value: formatTime12(d.timestamp) },
    { label: "Mixes", value: d.mixes },
    { label: "Bricks Produced", value: d.bricks_produced, bold: true },
    { label: "Labourers", value: d.labourers },
    { label: "Misc Expense", value: `${money(d.misc_amount)} (${d.misc_note || "—"})` },
  ]);
  card.innerHTML = `
    <h2>Today's Saved Entry</h2>
    ${table}
    ${d.is_corrected === "yes" ? "<p style=\"color:var(--muted);\"><em>This entry has been corrected.</em></p>" : ""}
  `;
}

// -------------------- Preview (Step 1) --------------------
// POST /manager/production/preview body {mixes, bricks_produced} -> {mixes, bricks_produced, calculated_field}
async function previewEntry() {
  const mixesRaw = document.getElementById("mixesInput").value.trim();
  const bricksRaw = document.getElementById("bricksInput").value.trim();

  const body = {
    mixes: mixesRaw === "" ? null : parseInt(mixesRaw, 10),
    bricks_produced: bricksRaw === "" ? null : parseInt(bricksRaw, 10),
  };

  try {
    const d = await apiFetch("/manager/production/preview", { method: "POST", body });
    if (mixesRaw !== document.getElementById("mixesInput").value.trim() || bricksRaw !== document.getElementById("bricksInput").value.trim()) return;
    currentPreview = d;

    const table = kvTable([
      { label: "Mixes", value: d.mixes, bold: true },
      { label: "Bricks Produced", value: d.bricks_produced, bold: true },
      { label: d.calculated_field === "none" ? "Average Bricks per Mix" : "Average Bricks per Mix (estimated)",
        value: d.avg_bricks_per_mix ?? "N/A", bold: true },
    ]);
    let note = d.calculated_field !== "none"
      ? `<p style="color:var(--muted);"><em>Note: '${d.calculated_field}' was auto-calculated, not typed.</em></p>`
      : "";

    document.getElementById("previewDetails").innerHTML = `${table}${note}`;
    document.getElementById("previewOutput").classList.remove("hidden");
  } catch (e) { showMessage(msgEl, e.message, true); }
}

// -------------------- Save (Step 2) --------------------
// POST /manager/production/save -> {message, mixes_delta_applied, is_correction}
async function saveEntry(confirmOverwrite = false) {
  if (!currentPreview) return showMessage(msgEl, "Preview an entry first.", true);

  const labourersRaw = document.getElementById("labourersInput").value.trim();
  if (labourersRaw === "") return showMessage(msgEl, "Enter number of labourers.", true);

  const miscAmountRaw = document.getElementById("miscAmountInput").value.trim();

  const body = {
    mixes: currentPreview.mixes,
    bricks_produced: currentPreview.bricks_produced,
    calculated_field: currentPreview.calculated_field,
    labourers: parseInt(labourersRaw, 10),
    misc_amount: miscAmountRaw === "" ? 0 : parseFloat(miscAmountRaw),
    misc_note: document.getElementById("miscNoteInput").value,
    confirm_overwrite: confirmOverwrite,
  };

  try {
    const d = await apiFetch("/manager/production/save", { method: "POST", body });
    showMessage(msgEl, d.message);
    document.getElementById("previewOutput").classList.add("hidden");
    document.getElementById("mixesInput").value = "";
    document.getElementById("bricksInput").value = "";
    document.getElementById("labourersInput").value = "";
    document.getElementById("miscAmountInput").value = "";
    document.getElementById("miscNoteInput").value = "";
    currentPreview = null;
    sessionUI.discard(['mixesInput', 'bricksInput', 'labourersInput', 'miscAmountInput', 'miscNoteInput']);
    await sessionUI.afterSave(checkExistingEntry);
  } catch (e) {
    if (e.message.includes("already exists")) {
      if (await confirmAction(e.message)) {
        return saveEntry(true);
      }
      showMessage(msgEl, "Save cancelled. Previous entry kept unchanged.", true);
    } else if (typeof e.message === "string" && e.message.includes("shortfalls")) {
      showMessage(msgEl, "Not enough stock to save this entry. Check the Stock tab.", true);
    } else {
      showMessage(msgEl, e.message, true);
    }
  }
}

// -------------------- Stock --------------------
// GET /manager/stock -> {material: {quantity, unit}}
async function loadStock() {
  const stock = await apiFetch("/manager/stock");
  const tbody = document.querySelector("#stockTable tbody");
  tbody.innerHTML = "";
  for (const [material, info] of Object.entries(stock)) {
    tbody.innerHTML += `<tr><td>${material}</td><td>${info.quantity} ${info.unit}</td></tr>`;
  }
}

// POST /manager/stock/refill body {material, amount} -> {material, added, unit, new_total}
async function refillStock() {
  const material = document.getElementById("refillMaterial").value;
  const amount = parseInt(document.getElementById("refillAmount").value, 10);
  if (!amount || amount <= 0) return showMessage(msgEl, "Enter a valid whole number.", true);
  try {
    const d = await apiFetch("/manager/stock/refill", { method: "POST", body: { material, amount } });
    showMessage(msgEl, `${material} updated: +${d.added} ${d.unit} (new total: ${d.new_total} ${d.unit})`);
    document.getElementById("refillAmount").value = "";
    sessionUI.discard(["refillMaterial", "refillAmount"]);
    await sessionUI.afterSave(loadStock);
  } catch (e) { showMessage(msgEl, e.message, true); }
}

// GET /manager/bricks-per-mix -> {bricks_per_mix}
async function loadBricksPerMix() {
  const d = await apiFetch("/manager/bricks-per-mix");
  document.getElementById("bricksPerMixCurrent").textContent = d.bricks_per_mix;
}

// PUT /manager/bricks-per-mix body {new_value} -> {old_value, new_value}
async function updateBricksPerMix() {
  const newValue = parseFloat(document.getElementById("bricksPerMixNew").value);
  if (!newValue || newValue <= 0) return showMessage(msgEl, "Enter a valid value.", true);
  try {
    const d = await apiFetch("/manager/bricks-per-mix", { method: "PUT", body: { new_value: newValue } });
    showMessage(msgEl, `Bricks-per-mix updated: ${d.old_value} → ${d.new_value}`);
    document.getElementById("bricksPerMixNew").value = "";
    sessionUI.discard(["bricksPerMixNew"]);
    await sessionUI.afterSave(loadBricksPerMix);
  } catch (e) { showMessage(msgEl, e.message, true); }
}

// -------------------- Utility Bills --------------------
// POST /manager/utility-bills body {bill_type, amount, confirm_overwrite} -> {bill_type, month, amount, was_correction}
async function submitUtilityBill(confirmOverwrite) {
  const bill_type = document.getElementById("utilityType").value;
  const amount = parseFloat(document.getElementById("utilityAmount").value);
  if (!amount || amount <= 0) return showMessage(msgEl, "Enter a valid amount.", true);

  try {
    const d = await apiFetch("/manager/utility-bills", {
      method: "POST",
      body: { bill_type, amount, billing_month: document.getElementById("utilityMonth").value || null, confirm_overwrite: confirmOverwrite },
    });
    showMessage(msgEl, `${d.bill_type} bill of ${money(d.amount)} saved for ${d.month}.`);
    document.getElementById("utilityAmount").value = "";
    sessionUI.discard(["utilityAmount"]);
    await sessionUI.afterSave(loadUtilityBills);
  } catch (e) {
    if (e.message.includes("already exists")) {
      if (await confirmAction(e.message)) {
        return submitUtilityBill(true);
      }
      showMessage(msgEl, "Action cancelled. Existing bill kept unchanged.", true);
    } else {
      showMessage(msgEl, e.message, true);
    }
  }
}

// -------------------- Brick Sales --------------------
// GET /manager/sales/outlet-stock -> {total_bricks}
async function loadOutletStock() {
  const d = await apiFetch("/manager/sales/outlet-stock");
  document.getElementById("outletStockValue").textContent = d.total_bricks.toLocaleString("en-IN");
  document.getElementById("curingStockValue").textContent = d.curing.toLocaleString("en-IN");
  document.getElementById("earlySaleStockValue").textContent = d.early_sale.toLocaleString("en-IN");
  document.getElementById("fullyCuredStockValue").textContent = d.fully_cured.toLocaleString("en-IN");
  document.getElementById("saleableStockValue").textContent = d.saleable.toLocaleString("en-IN");
  renderBatchRows(document.querySelector("#brickBatchesTable tbody"), d.batches);
  populateAdjustmentBatches(d.batches);
  return d;
}

function batchLabel(batch) {
  if (batch.source === "opening") return "Opening stock";
  if (batch.source === "production") return `Production #${batch.batch_id}`;
  if (batch.source === "return") return `Return #${batch.batch_id}`;
  return `Transfer #${batch.batch_id}`;
}

function stageLabel(stage) {
  return stage === "curing" ? "Curing" : stage === "early_sale" ? "Early-sale eligible" : "Fully cured";
}

function renderBatchRows(tbody, batches) {
  tbody.replaceChildren();
  for (const batch of batches) {
    const row = document.createElement("tr");
    const values = [
      batchLabel(batch), batch.production_date || batch.received_date,
      batch.age_days === null ? "Received cured" : `${batch.age_days} day${batch.age_days === 1 ? "" : "s"}`,
      stageLabel(batch.stage), Number(batch.remaining_quantity).toLocaleString("en-IN"),
    ];
    for (const value of values) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    }
    tbody.append(row);
  }
}

function populateAdjustmentBatches(batches) {
  const select = document.getElementById("adjustBatchId");
  if (!select) return;
  const selected = select.value;
  select.replaceChildren();
  for (const batch of batches) {
    const option = document.createElement("option");
    option.value = batch.batch_id;
    option.textContent = `${batchLabel(batch)} · ${stageLabel(batch.stage)} · ${Number(batch.remaining_quantity).toLocaleString("en-IN")} bricks`;
    select.append(option);
  }
  if ([...select.options].some(option => option.value === selected)) select.value = selected;
}

function updateAdjustmentForm() {
  const removesStock = ["damage", "transfer_out"].includes(document.getElementById("adjustKind").value);
  document.getElementById("adjustBatchWrap").classList.toggle("hidden", !removesStock);
}

// GET /manager/sales/default-price -> {default_cost_per_brick}
async function prefillDefaultPrice() {
  if (editingSaleId !== null || sessionUI.has("saleCostPerBrick")) return; // don't overwrite a value being edited
  const d = await apiFetch("/manager/sales/default-price");
  if (editingSaleId !== null || sessionUI.has("saleCostPerBrick")) return;
  document.getElementById("saleCostPerBrick").value = d.default_cost_per_brick;
  recalculateSale();
}

// Recomputes amount due / total, and only reveals Submit once everything is filled.
function recalculateSale() {
  const bricks = parseInt(document.getElementById("saleBricksPurchased").value, 10);
  const costPerBrick = parseFloat(document.getElementById("saleCostPerBrick").value);
  const otherCharges = parseFloat(document.getElementById("saleOtherCharges").value) || 0;
  const amountPaidRaw = document.getElementById("saleAmountPaid").value;

  const box = document.getElementById("saleCalculatedBox");
  const submitBtn = document.getElementById("saleSubmitBtn");

  if (!bricks || bricks <= 0 || !costPerBrick || costPerBrick <= 0) {
    box.classList.add("hidden");
    submitBtn.classList.add("hidden");
    return;
  }

  const amountDue = bricks * costPerBrick;
  const totalAmount = amountDue + otherCharges;

  document.getElementById("saleAmountDue").textContent = money(amountDue);
  document.getElementById("saleTotalAmount").textContent = money(totalAmount);
  box.classList.remove("hidden");

  // Submit only appears once amount paid has also been entered.
  if (amountPaidRaw !== "" && parseFloat(amountPaidRaw) >= 0) {
    submitBtn.classList.remove("hidden");
    submitBtn.textContent = editingSaleId !== null ? "Update Sale" : "Submit Sale";
  } else {
    submitBtn.classList.add("hidden");
  }
}

function clearSaleForm() {
  sessionUI.discard(['saleCustomerName', 'saleCustomerMobile', 'saleBricksPurchased', 'saleCostPerBrick', 'saleOtherCharges', 'saleAmountPaid']);
  sessionUI.saleCleared();
  document.getElementById("saleCustomerName").value = "";
  document.getElementById("saleCustomerMobile").value = "";
  document.getElementById("saleBricksPurchased").value = "";
  document.getElementById("saleOtherCharges").value = "0";
  document.getElementById("saleAmountPaid").value = "";
  document.getElementById("saleCalculatedBox").classList.add("hidden");
  document.getElementById("saleSubmitBtn").classList.add("hidden");
  editingSaleId = null;
  prefillDefaultPrice().catch(e => showMessage(msgEl, e.message, true));
}

// POST /manager/sales (new) or PUT /manager/sales/{id} (editing)
async function submitSale() {
  const customer_name = document.getElementById("saleCustomerName").value.trim();
  const customer_mobile = document.getElementById("saleCustomerMobile").value.trim();
  const bricks_purchased = parseInt(document.getElementById("saleBricksPurchased").value, 10);
  const cost_per_brick = parseFloat(document.getElementById("saleCostPerBrick").value);
  const other_charges = parseFloat(document.getElementById("saleOtherCharges").value) || 0;
  const amount_paid = parseFloat(document.getElementById("saleAmountPaid").value);

  if (!customer_name || !customer_mobile) {
    return showMessage(msgEl, "Enter the customer's name and mobile number.", true);
  }

  const body = { customer_name, customer_mobile, bricks_purchased, cost_per_brick, other_charges, amount_paid };

  try {
    if (editingSaleId !== null) {
      await apiFetch(`/manager/sales/${editingSaleId}`, { method: "PUT", body });
      showMessage(msgEl, "Sale updated.");
    } else {
      await apiFetch("/manager/sales", { method: "POST", body });
      showMessage(msgEl, "Sale recorded.");
    }
    clearSaleForm();
    await sessionUI.afterSave(() => Promise.all([loadOutletStock(), loadTodaysSales()]));
  } catch (e) {
    showMessage(msgEl, e.message, true);
  }
}

// GET /manager/sales/today -> {sales: [...]}
async function loadTodaysSales() {
  const d = await apiFetch("/manager/sales/today");
  const tbody = document.querySelector("#salesTable tbody");
  tbody.replaceChildren();
  for (const s of d.sales) {
    textRow(tbody, [formatTime12(s.timestamp), s.customer_name + (s.is_edited === "yes" ? " (edited)" : ""), s.customer_mobile, s.bricks_purchased, money(s.total_amount), money(s.amount_paid)],
      [["Edit", "pencil", () => editSale(s)], ["Print Receipt", "printer", () => openReceipt(s.sale_id)]]);
  }
  refreshIcons();
}

// Opens the PDF receipt in a new tab — user can view, print, or save from there.
function openReceipt(saleId) {
  return openPDF(`/manager/sales/${saleId}/receipt`, `receipt_${saleId}.pdf`);
}

function editSale(sale) {
  editingSaleId = sale.sale_id;
  document.getElementById("saleCustomerName").value = sale.customer_name;
  document.getElementById("saleCustomerMobile").value = sale.customer_mobile;
  document.getElementById("saleBricksPurchased").value = sale.bricks_purchased;
  document.getElementById("saleCostPerBrick").value = sale.cost_per_brick;
  document.getElementById("saleOtherCharges").value = sale.other_charges;
  document.getElementById("saleAmountPaid").value = sale.amount_paid;
  ['saleCustomerName', 'saleCustomerMobile', 'saleBricksPurchased', 'saleCostPerBrick', 'saleOtherCharges', 'saleAmountPaid'].forEach(id => sessionUI.record(document.getElementById(id)));
  recalculateSale();
  document.getElementById("saleCustomerName").scrollIntoView({ behavior: "smooth", block: "center" });
  showMessage(msgEl, `Editing sale for ${sale.customer_name}. Change the fields and click Update Sale.`);
}

// -------------------- Manual Stock Adjustment --------------------
// POST /manager/sales/adjust-stock body {change_amount, note} -> {change_amount, new_total}
async function submitStockAdjustment() {
  const enteredAmount = parseInt(document.getElementById("adjustChangeAmount").value, 10);
  const kind = document.getElementById("adjustKind").value;
  const removesStock = ["damage", "transfer_out"].includes(kind);
  const changeAmount = removesStock ? -enteredAmount : enteredAmount;
  const batchId = removesStock ? parseInt(document.getElementById("adjustBatchId").value, 10) : null;
  const note = document.getElementById("adjustNote").value.trim();

  if (!enteredAmount || enteredAmount <= 0) return showMessage(msgEl, "Enter a positive number of bricks.", true);
  if (removesStock && !batchId) return showMessage(msgEl, "Select the affected batch.", true);
  if (!note) return showMessage(msgEl, "Enter a note explaining this adjustment.", true);

  try {
    const d = await apiFetch("/manager/sales/adjust-stock", {
      method: "POST",
      body: { change_amount: changeAmount, kind, batch_id: batchId, note },
    });
    showMessage(msgEl, `Stock adjusted by ${d.change_amount > 0 ? "+" : ""}${d.change_amount}. New total: ${d.new_total}.`);
    document.getElementById("adjustChangeAmount").value = "";
    document.getElementById("adjustNote").value = "";
    sessionUI.discard(["adjustChangeAmount", "adjustNote"]);
    await sessionUI.afterSave(() => Promise.all([loadOutletStock(), loadAdjustmentHistory()]));
  } catch (e) { showMessage(msgEl, e.message, true); }
}

// GET /manager/sales/stock-adjustments -> {adjustments: [...]}
async function loadAdjustmentHistory() {
  const d = await apiFetch("/manager/sales/stock-adjustments");
  const tbody = document.querySelector("#adjustmentsTable tbody");
  tbody.innerHTML = "";
  d.adjustments.forEach((a) => {
    const color = a.change_amount > 0 ? "var(--ok)" : "var(--bad)";
    tbody.innerHTML += `<tr>
      <td>${formatTime12(a.time)}</td>
      <td style="color:${color};">${a.change_amount > 0 ? "+" : ""}${a.change_amount}</td>
      <td>${textHTML(a.note || "—")}</td><td>${a.resulting_stock}</td>
    </tr>`;
  });
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

  // Debounced so it doesn't fire an API call on every keystroke.
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

// -------------------- Navigation & Init --------------------
onSectionLoad("adjustments", async () => { await loadOutletStock(); await loadAdjustmentHistory(); updateAdjustmentForm(); });
onSectionLoad("production", checkExistingEntry);
onSectionLoad("stock", () => Promise.all([loadStock(), loadBricksPerMix()]));
onSectionLoad("sales", () => Promise.all([loadOutletStock(), loadTodaysSales(), prefillDefaultPrice()]));




async function loadUtilityBills() {
  const output = document.getElementById("savedUtilityBills");
  output.textContent = "Loading saved bills…";
  try {
    const month = document.getElementById("utilityMonth").value;
    const d = await apiFetch(`/manager/utility-bills?month=${encodeURIComponent(month)}`);
    output.replaceChildren();
    for (const type of ["Electricity", "Water"]) {
      const bill = d.bills.find(b => b.bill_type === type);
      const line = document.createElement("p");
      line.textContent = bill ? `${type}: ${money(bill.amount)} — saved ${bill.entry_date} at ${formatTime12(bill.entry_time)}` : `${type}: no actual bill saved for ${d.month}; calculations use the configured default.`;
      output.append(line);
    }
  } catch (e) { output.textContent = "Saved bills could not be loaded."; showMessage(msgEl, e.message, true); }
}
// Use formatToParts to avoid locale-dependent separators.
const monthParts = new Intl.DateTimeFormat("en", {timeZone:"Asia/Kolkata",year:"numeric",month:"2-digit"}).formatToParts(new Date());
document.getElementById("utilityMonth").value = `${monthParts.find(p=>p.type === "year").value}-${monthParts.find(p=>p.type === "month").value}`;
onSectionLoad("utility", loadUtilityBills);

// Restore edit identity before loading defaults. Production always needs a fresh preview.
sessionUI.attach({
  getSaleId: () => editingSaleId,
  setSaleId: id => { editingSaleId = Number.isInteger(id) ? id : null; },
  afterRestore: () => { recalculateSale(); updateAdjustmentForm(); },
});
for (const id of ["mixesInput", "bricksInput"]) {
  document.getElementById(id).addEventListener("input", () => {
    currentPreview = null;
    document.getElementById("previewOutput").classList.add("hidden");
  });
}
(async function init() {
  try { refreshIcons(); await initSectionNav("production"); }
  catch (e) { showMessage(msgEl, e.message, true); }
})();
