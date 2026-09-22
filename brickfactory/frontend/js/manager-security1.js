requireRole("manager");
document.getElementById("whoami").textContent = `${sessionStorage.getItem("username")} (manager)`;

const msgEl = document.getElementById("msg");
let currentPreview = null; // holds {mixes, bricks_produced, calculated_field} between preview and save
let editingSaleId = null;   // null = creating a new sale, otherwise editing this sale_id

let entryWindow = null;
let acceptedEntryDate = '';
let saleSaving = false;
const displayEntryDate = value => value.split('-').reverse().join('-');
function updateEntryLabels() {
  const day = document.getElementById('productionDate').value;
  if (!day) return;
  document.getElementById('saleFormHeading').textContent = editingSaleId === null ? 'New sale' : 'Correct sale';
  document.getElementById('saleDateNotice').textContent = `Sale date: ${displayEntryDate(day)}. Money entered here is recorded as received on this date. Later payments are entered by admin in Customer Accounts.`;
  document.getElementById('selectedSalesHeading').textContent = `Sales · ${displayEntryDate(day)}`;
}
async function refreshEntryWindow() {
  const input = document.getElementById('productionDate');
  entryWindow = await apiFetch('/production-entry/settings');
  input.min = entryWindow.earliest_date; input.max = entryWindow.today;
  if (!input.value) input.value = entryWindow.today;
  if (!acceptedEntryDate) acceptedEntryDate = input.value;
  const yesterday = new Date(entryWindow.today + 'T12:00:00Z');
  yesterday.setUTCDate(yesterday.getUTCDate()-1);
  document.getElementById('entryYesterday').dataset.date = yesterday.toISOString().slice(0,10);
  document.getElementById('entryYesterday').disabled = yesterday.toISOString().slice(0,10) < input.min;
  document.getElementById('productionDateHelp').textContent = `Production and sales: ${displayEntryDate(input.min)} to ${displayEntryDate(input.max)}. Admin allows ${entryWindow.backdate_days} previous day(s).`;
  sessionUI.record(input);
  updateEntryLabels();
}
async function changeEntryDate() {
  const input = document.getElementById('productionDate');
  const next = input.value;
  if (saleSaving || !next || next < input.min || next > input.max) {
    input.value = acceptedEntryDate;
    sessionUI.record(input);
    return showMessage(msgEl, 'Choose a date within the admin allowance.', true);
  }
  if (next === acceptedEntryDate) return;
  const draftIds = ['mixesInput','bricksInput','labourersInput','labourHoursInput','miscAmountInput','miscNoteInput','saleCustomerName','saleCustomerMobile','saleBricksPurchased','saleCostPerBrick','saleTransportRate','saleAmountPaid'];
  const hasDraft = draftIds.some(id => document.getElementById(id).value !== '') || [...document.querySelectorAll('[data-labour]')].some(el => el.value !== '') || editingSaleId !== null;
  if (hasDraft && !confirm(`Change entry date to ${displayEntryDate(next)}? Unsaved production and sale entries will be cleared.`)) {
    input.value = acceptedEntryDate; sessionUI.record(input); return;
  }
  if (hasDraft) {
    for (const id of draftIds) document.getElementById(id).value = '';
    sessionUI.discard([...draftIds,'labourGroupsDraft','labourManualMode']);
    resetLabourGroups(); clearSaleForm();
  }
  acceptedEntryDate = next;
  currentPreview = null;
  document.getElementById('previewOutput').classList.add('hidden');
  sessionUI.record(input); updateEntryLabels();
  document.querySelector('#salesTable tbody').replaceChildren();
  document.getElementById('selectedSalesStatus').textContent = 'Loading…';
  document.getElementById('existingEntryCard').textContent = 'Loading…';
  try { await Promise.all([checkExistingEntry(), loadTodaysSales()]); }
  catch(e) { showMessage(msgEl, e.message, true); }
}
async function checkExistingEntry() {
  await refreshEntryWindow();
  const input = document.getElementById('productionDate');
  if (input.value < input.min || input.value > input.max) {
    document.getElementById('existingEntryCard').textContent = 'This date is outside the current allowance. Select an available date.';
    return;
  }
  const selectedDate = input.value;
  const d = await apiFetch('/manager/production/today?date=' + encodeURIComponent(selectedDate));
  if (input.value !== selectedDate) return;
  const card = document.getElementById("existingEntryCard");
  if (!d.exists) {
    card.innerHTML = "<h2>Selected Date’s Saved Entry</h2><p style=\"color:var(--muted);\">No entry saved for this date.</p>";
    return;
  }
  const table = kvTable([
    { label: "Saved At", value: formatTime12(d.timestamp) },
    { label: "Mixes", value: d.mixes },
    { label: "Bricks Produced", value: d.bricks_produced, bold: true },
    { label: "Labourers", value: d.labourers },
    {label:"Total working hours",value:d.labour_hours ?? "Not recorded"},
    {label:"Labour cost",value:d.labour_cost===null?"Hours needed":money(d.labour_cost)},
    { label: "Misc Expense", value: `${money(d.misc_amount)} (${d.misc_note || "—"})` },
  ]);
  card.innerHTML = `
    <h2>Selected Date’s Saved Entry</h2>
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
    production_date: document.getElementById('productionDate').value,
    mixes: mixesRaw === "" ? null : parseInt(mixesRaw, 10),
    bricks_produced: bricksRaw === "" ? null : parseInt(bricksRaw, 10),
  };

  try {
    const d = await apiFetch("/manager/production/preview", { method: "POST", body });
    if (mixesRaw !== document.getElementById("mixesInput").value.trim() || bricksRaw !== document.getElementById("bricksInput").value.trim()) return;
    if (body.production_date !== document.getElementById('productionDate').value) return;
    currentPreview = d;

    const table = kvTable([
      { label: "Production date", value: d.production_date.split("-").reverse().join("-") },
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
  let groups;try{groups=readLabourGroups();}catch(e){return showMessage(msgEl,e.message,true);}
  const hoursRaw=document.getElementById("labourHoursInput").value.trim();
  if(hoursRaw===""||!Number.isFinite(Number(hoursRaw))||Number(hoursRaw)<0)return showMessage(msgEl,"Enter total person-hours worked.",true);

  const miscAmountRaw = document.getElementById("miscAmountInput").value.trim();

  const body = {
    production_date: currentPreview.production_date,
    mixes: currentPreview.mixes,
    bricks_produced: currentPreview.bricks_produced,
    calculated_field: currentPreview.calculated_field,
    labourers: labourersRaw===""?0:parseInt(labourersRaw, 10),
    labour_hours: Number(hoursRaw),
    labour_groups: groups,
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
    document.getElementById("labourHoursInput").value = "";
    resetLabourGroups();
    document.getElementById("miscAmountInput").value = "";
    document.getElementById("miscNoteInput").value = "";
    currentPreview = null;
    sessionUI.discard(['mixesInput', 'bricksInput', 'labourersInput', 'labourHoursInput', 'labourGroupsDraft', 'labourManualMode', 'miscAmountInput', 'miscNoteInput']);
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
    tbody.innerHTML += `<tr><td>${material}</td><td>${["Flyash", "Sand"].includes(material) ? `${Number((info.quantity / 1000).toFixed(3))} tonnes (${info.quantity} kg)` : `${info.quantity} ${info.unit}`}</td></tr>`;
  }
}

// POST /manager/stock/refill body {material, amount} -> {material, added, unit, new_total}
async function refillStock() {
  const material = document.getElementById("refillMaterial").value;
  const amount = Number(document.getElementById("refillAmount").value);
  if (!Number.isFinite(amount) || amount <= 0) return showMessage(msgEl, "Enter a positive quantity (decimals allowed).", true);
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
  // New sales always require an explicitly entered price. Existing drafts/edits retain theirs.
  recalculateSale();
}

// Recomputes amount due / total, and only reveals Submit once everything is filled.
let salePreviewTimer;
let salePreviewVersion = 0;
let salePreview = null;
function salePricingInput() {
  return {
    pricing_mode: document.getElementById('salePricingMode').value,
    bricks_purchased: Number(document.getElementById('saleBricksPurchased').value),
    cost_per_brick: document.getElementById('saleCostPerBrick').value,
    other_charges: document.getElementById('saleOtherCharges').value || '0',
    transport_mode: document.getElementById('saleTransportMode').value,
    transport_rate: document.getElementById('saleTransportMode').value === 'none' ? '0' : document.getElementById('saleTransportRate').value
  };
}
function recalculateSale() {
  clearTimeout(salePreviewTimer);
  const version = ++salePreviewVersion;
  salePreview = null;
  const input = salePricingInput();
  const legacy = input.pricing_mode === 'legacy_inclusive';
  const delivered = input.pricing_mode === 'delivered_base';
  const suffix = legacy ? 'includes GST' : 'before GST';
  document.getElementById('salePriceLabel').textContent = `${delivered ? 'Delivered price' : 'Brick price'} per brick · ₹, ${suffix}`;
  document.getElementById('saleOtherLabel').textContent = `Other charges · ₹, ${suffix}`;
  document.getElementById('saleTransportFields').hidden = input.transport_mode === 'none';
  document.getElementById('saleTransportRateLabel').textContent = `${input.transport_mode === 'per_brick' ? 'Driver charge per brick' : 'Total driver charge for this sale'} · ₹, ${suffix}`;
  document.getElementById('saleTransportHint').textContent = legacy
    ? 'Existing bill: values include GST. Choose a pre-GST method and enter the agreed amounts to correct it.'
    : delivered ? 'Driver charge is already within the delivered price. We subtract it to find the brick value, then add GST once.'
    : 'Enter the driver payment before GST. It is added to the brick value and excluded from profit.';
  const box = document.getElementById('saleCalculatedBox');
  const status = document.getElementById('salePricingStatus');
  const button = document.getElementById('saleSubmitBtn');
  button.disabled = true;
  box.classList.add('hidden');
  status.textContent = '';
  const ids = ['saleBricksPurchased','saleCostPerBrick','saleOtherCharges'];
  if (input.transport_mode !== 'none') ids.push('saleTransportRate');
  if (ids.some(id => !document.getElementById(id).checkValidity()) || !input.bricks_purchased || !input.cost_per_brick || (input.transport_mode !== 'none' && !input.transport_rate)) return;
  status.textContent = 'Calculating…';
  salePreviewTimer = setTimeout(async () => {
    try {
      const d = await apiFetch('/manager/sales/preview', {method:'POST', body:input, busy:false});
      if (version !== salePreviewVersion) return;
      salePreview = {key:JSON.stringify(input), data:d};
      status.textContent = '';
      const rate = value => Number(value).toLocaleString('en-IN', {minimumFractionDigits:2,maximumFractionDigits:6});
      document.getElementById('saleTransportSummary').textContent = legacy
        ? `Transportation including GST: ${money(d.transport_amount)}`
        : `Driver payment: ${money(d.transport_base_amount)} ÷ ${input.bricks_purchased} bricks = ₹${rate(d.transport_per_brick)}/brick. Brick price: ₹${rate(d.base_unit_price)} + transport: ₹${rate(d.transport_per_brick)} = ₹${rate(d.delivered_base_price)}/brick before GST (excluding other charges).`;
      const breakdown = document.getElementById('saleGstBreakdown');
      breakdown.replaceChildren();
      const rows = legacy ? [['Before GST', d.taxable_amount], ['GST included (12%)', d.gst_amount]] : [
        ['Bricks before GST', d.brick_base_amount], ['Driver payment', d.transport_base_amount],
        ['Other charges before GST', d.other_base_amount], ['Subtotal before GST', d.taxable_amount],
        ['GST on bricks', d.brick_gst], ['GST on transportation', d.transport_gst],
        ['GST on other charges', d.other_gst], ['Total GST (12%)', d.gst_amount]
      ];
      for (const [label, amount] of rows) {
        const term = document.createElement('dt'); term.textContent = label;
        const value = document.createElement('dd'); value.textContent = money(amount); value.style.margin = '0';
        breakdown.append(term, value);
      }
      document.getElementById('saleBrickAmountLabel').textContent = legacy ? 'Bricks including GST' : 'Revenue excluding GST and driver payment';
      document.getElementById('saleAmountDue').textContent = money(legacy ? d.amount_due : Number(d.taxable_amount) - Number(d.transport_base_amount));
      document.getElementById('saleTotalAmount').textContent = money(d.total_amount);
      box.classList.remove('hidden');
      const paid = document.getElementById('saleAmountPaid');
      button.disabled = saleSaving || paid.value === '' || !paid.checkValidity();
      button.textContent = editingSaleId !== null ? 'Update Sale' : 'Submit Sale';
    } catch (error) {
      if (version !== salePreviewVersion) return;
      status.textContent = error.message || 'Unable to calculate. Check the amounts and your connection.';
    }
  }, 180);
}

function clearSaleForm() {
  sessionUI.discard(['saleCustomerName', 'saleCustomerMobile', 'saleBricksPurchased', 'saleCostPerBrick', 'saleOtherCharges', 'salePricingMode', 'saleTransportMode', 'saleTransportRate', 'saleAmountPaid', 'saleCustomerAccount']);
  sessionUI.saleCleared();
  document.getElementById("saleCustomerName").value = "";
  document.getElementById("saleCustomerMobile").value = "";
  document.getElementById("saleBricksPurchased").value = "";
  document.getElementById("saleCostPerBrick").value = "";
  document.getElementById("saleOtherCharges").value = "0";
  document.getElementById("salePricingMode").value = "brick_base";
  document.getElementById('saleTransportMode').value = 'none';
  document.getElementById('saleTransportRate').value = '';
  document.getElementById("saleAmountPaid").value = "";
  document.getElementById("saleCalculatedBox").classList.add("hidden");
  document.getElementById("saleSubmitBtn").disabled = true;
  editingSaleId = null;
  updateEntryLabels();
  if(window.resetSaleAccount)window.resetSaleAccount();
  prefillDefaultPrice().catch(e => showMessage(msgEl, e.message, true));
}

// POST /manager/sales (new) or PUT /manager/sales/{id} (editing)
async function submitSale() {
  if (saleSaving) return;
  const pricing = salePricingInput();
  if (!salePreview || salePreview.key !== JSON.stringify(pricing)) return showMessage(msgEl, 'Wait for the current price calculation before saving.', true);
  if (editingSaleId !== null && !confirm(`Update this bill to ${money(salePreview.data.total_amount)} including GST? The customer account balance will be recalculated.`)) return;
  const dateInput = document.getElementById('productionDate');
  const sale_date = dateInput.value;
  if (!sale_date || !dateInput.checkValidity()) return showMessage(msgEl, 'Select an allowed entry date first.', true);
  const customer_name = document.getElementById("saleCustomerName").value.trim();
  const customer_mobile = document.getElementById("saleCustomerMobile").value.trim();
  const bricks_purchased = parseInt(document.getElementById("saleBricksPurchased").value, 10);
  const cost_per_brick = parseFloat(document.getElementById("saleCostPerBrick").value);
  const other_charges = parseFloat(document.getElementById("saleOtherCharges").value) || 0;
  const amount_paid = parseFloat(document.getElementById("saleAmountPaid").value);

  if (!document.getElementById("saleCustomerAccount").value && !customer_name && !customer_mobile) {
    return showMessage(msgEl, "Enter the customer's name or phone number, or select an existing account.", true);
  }

  const transport_mode = document.getElementById('saleTransportMode').value;
  const transport_rate = transport_mode === 'none' ? 0 : Number(document.getElementById('saleTransportRate').value);
  if (transport_mode !== 'none' && (!document.getElementById('saleTransportRate').checkValidity() || !Number.isFinite(transport_rate) || transport_rate <= 0)) return showMessage(msgEl,'Enter a valid transport charge.',true);
  const body = { sale_date, transport_mode, transport_rate, customer_id:Number(document.getElementById("saleCustomerAccount").value)||null,request_id:window.saleAccountRequestId(),customer_name, customer_mobile, bricks_purchased, cost_per_brick, other_charges, amount_paid, ...pricing };

  if (entryWindow && sale_date !== entryWindow.today && !confirm(`Save this sale and its money received for ${displayEntryDate(sale_date)}?`)) return;
  saleSaving = true; dateInput.disabled = true;
  document.getElementById('saleSubmitBtn').disabled = true;
  try {
    if (editingSaleId !== null) {
      await apiFetch(`/manager/sales/${editingSaleId}`, { method: "PUT", body });
      showMessage(msgEl, `Sale updated for ${displayEntryDate(sale_date)}.`);
    } else {
      await apiFetch("/manager/sales", { method: "POST", body });
      showMessage(msgEl, `Sale recorded for ${displayEntryDate(sale_date)}.`);
    }
    clearSaleForm();
    await sessionUI.afterSave(() => Promise.all([loadOutletStock(), loadTodaysSales(),loadSaleCustomers()]));
  } catch (e) {
    showMessage(msgEl, e.message, true);
  } finally {
    saleSaving = false; dateInput.disabled = false;
    recalculateSale();
  }
}

// GET /manager/sales/today -> {sales: [...]}
async function loadTodaysSales() {
  if (!entryWindow) await refreshEntryWindow();
  const selected = document.getElementById('productionDate').value;
  const d = await apiFetch('/manager/sales/today?date=' + encodeURIComponent(selected));
  if (selected !== document.getElementById('productionDate').value) return;
  updateEntryLabels();
  document.getElementById('selectedSalesStatus').textContent = d.sales.length ? `${d.sales.length} sale(s) saved.` : 'No sales saved for this date.';
  const tbody = document.querySelector("#salesTable tbody");
  tbody.replaceChildren();
  for (const s of d.sales) {
    textRow(tbody, [s.recorded_at ? new Date(s.recorded_at).toLocaleString('en-IN', {timeZone:'Asia/Kolkata',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}) : formatTime12(s.timestamp), s.customer_name + (s.is_edited === "yes" ? " (edited)" : ""), s.customer_mobile, s.bricks_purchased, money(s.total_amount), money(s.amount_received)],
      [["Edit", "pencil", () => editSale(s)], ["Print Receipt", "printer", () => openReceipt(s.sale_id)]]);
  }
  refreshIcons();
}

// Opens the PDF receipt in a new tab — user can view, print, or save from there.
function openReceipt(saleId) {
  return openPDF(`/manager/sales/${saleId}/receipt`, `receipt_${saleId}.pdf`);
}

function editSale(sale) {
  if (sale.sale_date !== document.getElementById('productionDate').value) return;
  editingSaleId = sale.sale_id;
  updateEntryLabels();
  document.getElementById("saleCustomerAccount").value=String(sale.customer_id);
  selectSaleCustomer();
  document.getElementById("saleCustomerName").value = sale.customer_name;
  document.getElementById("saleCustomerMobile").value = sale.customer_mobile;
  document.getElementById("saleBricksPurchased").value = sale.bricks_purchased;
  document.getElementById("salePricingMode").value = sale.pricing_mode || "legacy_inclusive";
  document.getElementById("saleCostPerBrick").value = sale.entered_unit_price ?? sale.cost_per_brick;
  document.getElementById("saleOtherCharges").value = sale.other_base_amount ?? sale.other_charges;
  document.getElementById('saleTransportMode').value = sale.transport_mode || 'none';
  document.getElementById('saleTransportRate').value = sale.transport_rate || '';
  document.getElementById("saleAmountPaid").value = sale.amount_received;
  ['saleCustomerName', 'saleCustomerMobile', 'saleBricksPurchased', 'saleCostPerBrick', 'saleOtherCharges', 'salePricingMode', 'saleTransportMode', 'saleTransportRate', 'saleAmountPaid', 'saleCustomerAccount', 'productionDate'].forEach(id => sessionUI.record(document.getElementById(id)));
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
  afterRestore: () => { restoreLabourGroups(); recalculateSale(); updateAdjustmentForm(); },
});
for (const id of ["mixesInput", "bricksInput", "productionDate"]) {
  document.getElementById(id).addEventListener("input", () => {
    currentPreview = null;
    document.getElementById("previewOutput").classList.add("hidden");
  });
}
document.getElementById('productionDate').addEventListener('change', changeEntryDate);
for (const [id, getDate] of [['entryToday', () => entryWindow?.today], ['entryYesterday', () => document.getElementById('entryYesterday').dataset.date]]) {
  document.getElementById(id).addEventListener('click', () => {
    if (saleSaving || !getDate()) return;
    document.getElementById('productionDate').value = getDate(); changeEntryDate();
  });
}
(async function init() {
  try { refreshIcons(); await initSectionNav("production"); await refreshEntryWindow(); }
  catch (e) { showMessage(msgEl, e.message, true); }
})();
