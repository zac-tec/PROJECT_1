/*
  API helper. If FastAPI is running somewhere other than localhost:8000
  (e.g. you're accessing from another device on your network), change
  API_BASE below to that address.
*/
const API_BASE = "";

function getRole() {
  return sessionStorage.getItem("role");
}

function logout() {
  if (typeof sessionUI !== "undefined") sessionUI.forget();
  sessionStorage.clear();
  window.location.href = "login.html";
}

function requireRole(role) {
  if (getRole() !== role) {
    window.location.href = "login.html";
  }
}

async function apiFetch(path, { method = "GET", body = null } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = sessionStorage.getItem("access_token");
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const buttons = method !== "GET" ? [...document.querySelectorAll("button:not(:disabled), main.content input:not(:disabled), main.content select:not(:disabled), main.content textarea:not(:disabled)")] : [];
  buttons.forEach(button => { button.disabled = true; button.setAttribute("aria-busy", "true"); });
  let res;
  try {
    res = await (typeof sessionUI !== "undefined" ? sessionUI.request : fetch)(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : null,
    });
  } finally {
    buttons.forEach(button => { button.disabled = false; button.removeAttribute("aria-busy"); });
  }

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map(item => `${(item.loc || []).filter(x => x !== "body").join(" ")}: ${item.msg}`).join("\n")
      : typeof data.detail === "string" ? data.detail : data.detail?.message || `Request failed (${res.status})`;
    throw new Error(detail || `Request failed (${res.status})`);
  }

  return data;
}

async function fetchPDF(path) {
  const token = sessionStorage.getItem("access_token");
  if (!token) throw new Error("Please sign in again to open this PDF.");
  const res = await (typeof sessionUI !== "undefined" ? sessionUI.request : fetch)(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    if (res.status === 401 || res.status === 403) {
      throw new Error("Your session expired or you do not have access. Please sign in again.");
    }
    const data = await res.json().catch(() => ({}));
    throw new Error(typeof data.detail === "string" ? data.detail : `Could not load PDF (${res.status}).`);
  }
  return res.blob();
}

async function openPDF(path, filename) {
  // Open during the click, before awaiting the request, to avoid popup blocking.
  const preview = window.open("about:blank", "_blank");
  if (preview) preview.opener = null;
  try {
    const blob = await fetchPDF(path);
    const url = URL.createObjectURL(blob);
    if (preview && !preview.closed) preview.location.href = url;
    else {
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
    }
    setTimeout(() => URL.revokeObjectURL(url), 300000);
  } catch (e) {
    if (preview && !preview.closed) preview.close();
    showMessage(msgEl, e.message, true);
  }
}

function money(n) {
  return `Rs. ${Number(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// -------------------- Unified Navigation --------------------
// Drives section switching for BOTH the desktop sidebar and the mobile
// bottom bar / drawer, from one place. Any element with [data-section]
// anywhere on the page (sidebar OR bottom-nav) participates automatically.
const _sectionLoadCallbacks = {};

function onSectionLoad(section, callback) {
  _sectionLoadCallbacks[section] = callback;
}

function activateSection(section, skipCallback = false) {
  if (!document.getElementById(`sec-${section}`)) return;
  document.querySelectorAll("main.content > section").forEach((s) => s.classList.add("hidden"));
  const target = document.getElementById(`sec-${section}`);
  if (target) target.classList.remove("hidden");
  document.querySelectorAll("[data-section]").forEach((b) => b.classList.toggle("active", b.dataset.section === section));
  closeDrawer();
  sessionUI.select(section);
  if (!skipCallback) return sessionUI.refresh(section, true);
}

function initSectionNav(defaultSection, skipDefaultCallback = false) {
  document.querySelectorAll("[data-section]").forEach((btn) => {
    btn.addEventListener("click", () => activateSection(btn.dataset.section));
  });
  sessionUI.initialize();
  if (defaultSection) {
    const section = sessionUI.initial(defaultSection);
    activateSection(section, true);
    return sessionUI.refresh(section);
  }
}

function toggleDrawer() {
  document.getElementById("sidebar").classList.toggle("open");
  document.getElementById("drawerOverlay").classList.toggle("open");
}

function closeDrawer() {
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("drawerOverlay");
  if (sidebar) sidebar.classList.remove("open");
  if (overlay) overlay.classList.remove("open");
}

let lastScrollY = 0;
window.addEventListener("scroll", () => {
  const nav = document.querySelector("nav.sidebar");
  if (!nav) return;
  const currentY = window.scrollY;
  nav.classList.toggle("nav-receded", currentY > lastScrollY && currentY > 80);
  lastScrollY = currentY;
}, { passive: true });
// -------------------- Daily Report Sharing (WhatsApp) --------------------
// Sends the text summary via a wa.me link, pre-filled to the configured
// client number — the user still taps "Send" themselves (WhatsApp/browsers
// don't allow that final step to be automated).
async function shareReportText() {
  try {
    const d = await apiFetch("/daily-report/summary-text");
    if (!d.whatsapp_number) {
      showMessage(msgEl, "No client WhatsApp number set yet — add one in Admin settings first.", true);
      return;
    }
    const cleanNumber = d.whatsapp_number.replace(/[^0-9]/g, "");
    window.open(`https://wa.me/${cleanNumber}?text=${encodeURIComponent(d.text)}`, "_blank");
  } catch (e) { showMessage(msgEl, e.message, true); }
}

// Generates the full PDF and opens the device's native share sheet so the
// user can pick WhatsApp and attach the file directly. Falls back to just
// opening the PDF (e.g. on desktop browsers without file-sharing support).
async function shareReportPDF() {
  try {
    const blob = await fetchPDF("/daily-report/pdf");
    const today = new Date().toISOString().slice(0, 10);
    const file = new File([blob], `daily_report_${today}.pdf`, { type: "application/pdf" });

    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      await navigator.share({ files: [file], title: "Daily Report", text: "Daily stock & production report" });
    } else {
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = file.name;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 300000);
    }
  } catch (e) {
    if (e.name !== "AbortError") showMessage(msgEl, e.message, true); // AbortError = user just cancelled the share sheet
  }
}

function showMessage(el, text, isError = false) {
  if (el) el.classList.add("hidden");
  return appDialog(isError ? "Unable to complete action" : "Update", text, false, isError);
}

// Builds a simple two-column Label | Value table from an array of row objects:
// { label, value, color (optional), bold (optional) }
// Used everywhere a report used to be shown as stacked <p> lines.
function textHTML(value) {
  const span = document.createElement("span");
  span.textContent = value ?? "";
  return span.innerHTML;
}

function textRow(tbody, values, actions = []) {
  const row = document.createElement("tr");
  for (const value of values) {
    const cell = document.createElement("td");
    cell.textContent = value ?? "";
    row.append(cell);
  }
  if (actions.length) {
    const cell = document.createElement("td");
    for (const [title, icon, callback] of actions) {
      const button = document.createElement("button");
      button.className = "icon-btn";
      button.title = title;
      button.setAttribute("aria-label", title);
      const glyph = document.createElement("i");
      glyph.dataset.lucide = icon;
      glyph.className = "icon";
      button.append(glyph);
      button.addEventListener("click", callback);
      cell.append(button);
    }
    row.append(cell);
  }
  tbody.append(row);
  return row;
}

function kvTable(rows) {
  const table = document.createElement("table");
  const body = document.createElement("tbody");
  table.append(body);
  for (const item of rows) {
    const row = textRow(body, [item.label, item.value]);
    const cell = row.lastElementChild;
    cell.style.textAlign = "right";
    if (item.color) cell.style.color = item.color;
    if (item.bold) cell.style.fontWeight = "700";
  }
  return table.outerHTML;
}

function customerResults(output, customers) {
  output.innerHTML = '<table><thead><tr><th>Name</th><th>Mobile</th><th>Total Bricks</th><th>Total Billed</th><th>Pending</th><th></th></tr></thead><tbody></tbody></table>';
  const body = output.querySelector("tbody");
  for (const customer of customers) {
    textRow(body, [customer.customer_name, customer.customer_mobile, customer.total_bricks, money(customer.total_billed), money(customer.pending_dues)],
      [["View purchase history", "history", () => showCustomerHistory(customer.customer_mobile)]]);
  }
  refreshIcons();
}

function customerOrders(output, summary, orders) {
  output.innerHTML = '<h2 style="margin-top:16px;">Purchase History</h2>' + summary + '<table style="margin-top:10px;"><thead><tr><th>Date</th><th>Bricks</th><th>Total</th><th>Balance</th><th></th></tr></thead><tbody></tbody></table>';
  const body = output.lastElementChild.querySelector("tbody");
  for (const order of orders) {
    textRow(body, [`${order.date} ${formatTime12(order.time)}`, order.bricks_purchased, money(order.total_amount), money(order.balance_due)],
      [["Print Receipt", "printer", () => openReceipt(order.sale_id)]]);
  }
}

// Converts a "HH:MM:SS" 24-hour string (as returned by the API) into a
// clean 12-hour "H:MM AM/PM" display string. Returns "" for empty input.
function formatTime12(hhmmss) {
  if (!hhmmss) return "";
  const parts = hhmmss.split(":");
  const h = parseInt(parts[0], 10);
  const m = parts[1] || "00";
  const period = h >= 12 ? "PM" : "AM";
  const hour12 = h % 12 === 0 ? 12 : h % 12;
  return `${hour12}:${String(m).padStart(2, "0")} ${period}`;
}

// Re-renders any <i data-lucide="..."> tags into actual SVG icons. Call
// this after injecting any new HTML that contains icon placeholders.
function refreshIcons() {
  if (window.lucide) lucide.createIcons();
}

/*
  Renders a table body where the value column is editable in place —
  click the pencil icon, the value becomes an input with Save/Cancel
  buttons right there in the row. No separate form, no page jump.

  rows: [{ key, label, rawValue, unit (optional) }]
  onSave: async (key, newValue) => {...}  — call the API here; throw on failure
  formatDisplay: (rawValue) => string — how to show the value when not editing
*/
function renderInlineEditTable(tbody, rows, onSave, formatDisplay = (v) => v, inputStep = "0.01") {
  tbody.innerHTML = "";
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${textHTML(row.label)}</td>
      <td class="inline-edit-cell">
        <span class="view-mode">${formatDisplay(row.rawValue)}</span>
        <input class="edit-mode hidden" type="number" step="${inputStep}" value="${row.rawValue}">
      </td>
      <td class="inline-edit-actions">
        <button class="icon-btn edit-trigger" title="Edit"><i data-lucide="pencil" class="icon"></i></button>
        <button class="icon-btn save save-trigger hidden" title="Save"><i data-lucide="check" class="icon"></i></button>
        <button class="icon-btn cancel cancel-trigger hidden" title="Cancel"><i data-lucide="x" class="icon"></i></button>
      </td>
    `;
    const viewSpan = tr.querySelector(".view-mode");
    const input = tr.querySelector("input");
    input.id = `inline-${tbody.id || tbody.closest("table").id}-${row.key}`;
    input.dataset.inlineDraft = "true";
    const editBtn = tr.querySelector(".edit-trigger");
    const saveBtn = tr.querySelector(".save-trigger");
    const cancelBtn = tr.querySelector(".cancel-trigger");

    const enterEditMode = () => {
      viewSpan.classList.add("hidden");
      input.classList.remove("hidden");
      editBtn.classList.add("hidden");
      saveBtn.classList.remove("hidden");
      cancelBtn.classList.remove("hidden");
      input.focus();
      input.select();
    };
    const exitEditMode = () => {
      viewSpan.classList.remove("hidden");
      input.classList.add("hidden");
      editBtn.classList.remove("hidden");
      saveBtn.classList.add("hidden");
      cancelBtn.classList.add("hidden");
    };

    editBtn.onclick = enterEditMode;
    cancelBtn.onclick = () => { sessionUI.discard([input.id]); input.value = row.rawValue; exitEditMode(); };
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") saveBtn.click();
      if (e.key === "Escape") cancelBtn.click();
    });
    saveBtn.onclick = async () => {
      const newValue = parseFloat(input.value);
      if (isNaN(newValue)) return;
      try {
        await onSave(row.key, newValue);
      } catch (e) {
        showMessage(msgEl, e.message, true);
      }
    };

    tbody.appendChild(tr);
    sessionUI.restore(tr);
  });
  refreshIcons();
}


// Queue messages so concurrent report failures cannot replace an open dialog.
let dialogQueue = Promise.resolve();
function appDialog(title, message, confirm = false, isError = false) {
  const result = dialogQueue.then(() => new Promise((resolve) => {
    const dialog = document.createElement("dialog");
    dialog.className = "app-dialog";
    dialog.setAttribute("aria-labelledby", "app-dialog-title");
    dialog.setAttribute("aria-describedby", "app-dialog-message");
    const heading = document.createElement("h2");
    heading.id = "app-dialog-title";
    heading.textContent = title;
    const content = document.createElement("p");
    content.id = "app-dialog-message";
    content.textContent = message.replace(/Resend with confirm_overwrite=true to replace it\./g, "");
    const actions = document.createElement("div");
    actions.className = "dialog-actions";
    if (confirm) {
      const cancel = document.createElement("button");
      cancel.textContent = "Keep existing";
      cancel.className = "secondary";
      cancel.autofocus = true;
      cancel.onclick = () => closeDialog("cancel");
      actions.append(cancel);
    }
    const ok = document.createElement("button");
    ok.textContent = confirm ? "Replace entry" : "OK";
    ok.className = "primary";
    ok.onclick = () => closeDialog("ok");
    actions.append(ok);
    dialog.append(heading, content, actions);
    document.body.append(dialog);
    let closing = false;
    const closeDialog = (value) => {
      if (closing) return;
      closing = true;
      dialog.returnValue = value;
      if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
        dialog.close();
        return;
      }
      dialog.classList.add("is-closing");
      dialog.addEventListener("animationend", () => dialog.close(), { once: true });
    };
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) closeDialog("cancel");
    });
    dialog.addEventListener("cancel", (event) => { event.preventDefault(); closeDialog("cancel"); });
    dialog.addEventListener("close", () => { const accepted = dialog.returnValue === "ok"; dialog.remove(); resolve(accepted); }, {once:true});
    dialog.showModal();
  }));
  dialogQueue = result.catch(() => {});
  return result;
}
function confirmAction(message) { return appDialog("Replace saved entry?", message, true); }
