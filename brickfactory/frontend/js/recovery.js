// Per-tab drafts, scoped to the signed-in account. Server results are never stored.
const sessionUI = (() => {
  const user = sessionStorage.getItem("username");
  const role = getRole();
  const key = `brickfactory-ui-v1:${role}:${user}`;
  let state = { fields: {}, section: null, saleId: null };
  try { Object.assign(state, JSON.parse(sessionStorage.getItem(key) || "{}")); } catch (_) {}
  state.fields ||= {};
  let recovery = null;
  let refreshing = false;
  let failures = 0;
  let adapter = {};
  let remembering = true;
  const valueOf = el => el.type === "checkbox" ? el.checked : el.value;
  function persist() {
    if (!remembering) return;
    try { sessionStorage.setItem(key, JSON.stringify(state)); }
    catch (_) { notice("Draft storage is unavailable. Keep this page open until your work is saved."); }
  }
  function notice(text) {
    let el = document.getElementById("recoveryStatus");
    if (!el) {
      el = document.createElement("div");
      el.id = "recoveryStatus";
      el.className = "card";
      el.setAttribute("role", "status");
      document.querySelector("main.content")?.prepend(el);
    }
    el.replaceChildren(document.createTextNode(text + " "));
    const button = document.createElement("button");
    button.textContent = "Refresh saved data";
    button.onclick = () => refresh();
    el.append(button);
    el.hidden = false;
  }
  function record(el) {
    if (!el.id || !el.closest("main.content > section") || el.type === "password") return;
    state.fields[el.id] = valueOf(el);
    if (["saleCustomerName", "saleCustomerMobile", "saleBricksPurchased", "saleCostPerBrick", "saleOtherCharges", "saleAmountPaid"].includes(el.id)) {
      for (const id of ["saleCustomerName", "saleCustomerMobile", "saleBricksPurchased", "saleCostPerBrick", "saleOtherCharges", "saleAmountPaid"]) {
        state.fields[id] = valueOf(document.getElementById(id));
      }
    }
    if (adapter.getSaleId) state.saleId = adapter.getSaleId();
    persist();
  }
  function restore(root = document) {
    for (const [id, value] of Object.entries(state.fields)) {
      const el = document.getElementById(id);
      if (!el || !root.contains(el)) continue;
      if (el.type === "checkbox") el.checked = Boolean(value);
      else el.value = value;
      if (el.dataset.inlineDraft) {
        const row = el.closest("tr");
        row.querySelectorAll(".view-mode, .edit-trigger").forEach(node => node.classList.add("hidden"));
        row.querySelectorAll(".edit-mode, .save-trigger, .cancel-trigger").forEach(node => node.classList.remove("hidden"));
      }
    }
  }
  function discard(ids) { ids.forEach(id => delete state.fields[id]); persist(); }
  function savedValue(id, value) {
    const el = document.getElementById(id);
    if (!el) return;
    const next = Object.hasOwn(state.fields, id) ? state.fields[id] : value;
    if (el.type === "checkbox") el.checked = Boolean(next); else el.value = next;
  }
  async function refresh(section = state.section, markSeen = false) {
    if (refreshing || !section) return;
    refreshing = true;
    const before = failures;
    try {
      await _sectionLoadCallbacks[section]?.(markSeen);
      if (before === failures) document.getElementById("recoveryStatus")?.setAttribute("hidden", "");
    } catch (error) {
      failed();
    } finally {
      restore(document.getElementById(`sec-${section}`) || document);
      adapter.afterRestore?.();
      refreshing = false;
      // Navigation during an outstanding load must also load the destination.
      if (section !== state.section) refresh(state.section);
    }
  }
  function failed() {
    failures++;
    notice("Saved data could not be refreshed. Displayed figures may be out of date; your draft is kept.");
  }
  async function afterSave(callback) {
    const before = failures;
    try { await callback(); } catch (_) { failed(); }
    if (before !== failures) {
      notice("Your changes were saved, but the display could not be refreshed. Refresh saved data; do not submit again.");
    }
  }
  function reauthenticate() {
    if (recovery) return recovery;
    recovery = new Promise(resolve => {
      const dialog = document.createElement("dialog");
      dialog.className = "app-dialog";
      const heading = document.createElement("h2");
      heading.id = "session-recovery-title";
      dialog.setAttribute("aria-labelledby", heading.id);
      heading.textContent = "Sign in to continue";
      const help = document.createElement("p");
      help.textContent = `Your session expired. Your entries are kept. Sign in as ${user} to continue.`;
      const form = document.createElement("form");
      const label = document.createElement("label");
      label.textContent = "Password";
      const password = document.createElement("input");
      password.type = "password";
      password.autocomplete = "current-password";
      password.required = true;
      label.append(password);
      const error = document.createElement("p");
      error.setAttribute("role", "alert");
      const submit = document.createElement("button");
      submit.type = "submit";
      submit.className = "primary";
      submit.textContent = "Sign in";
      const cancel = document.createElement("button");
      cancel.type = "button";
      cancel.className = "secondary";
      cancel.textContent = "Keep editing";
      cancel.onclick = () => dialog.close("cancel");
      const actions = document.createElement("div");
      actions.className = "dialog-actions";
      actions.append(cancel, submit);
      form.append(label, error, actions);
      form.onsubmit = async event => {
        event.preventDefault();
        submit.disabled = true;
        try {
          const response = await fetch("/login", {
            method: "POST", headers: {"Content-Type": "application/json"},
            body: JSON.stringify({username: user, password: password.value}),
          });
          const data = await response.json();
          if (!response.ok) throw new Error("Sign-in failed. Check your password and try again.");
          if (data.username !== user || data.role !== role || !data.access_token) {
            throw new Error("This account's access has changed. Sign out and sign in again.");
          }
          sessionStorage.setItem("access_token", data.access_token);
          dialog.close("ok");
        } catch (e) { error.textContent = e.message; }
        finally { password.value = ""; submit.disabled = false; }
      };
      dialog.append(heading, help, form);
      document.body.append(dialog);
      dialog.addEventListener("close", () => {
        const ok = dialog.returnValue === "ok";
        password.value = "";
        dialog.remove();
        resolve(ok);
      }, {once:true});
      dialog.showModal();
      password.focus();
    }).finally(() => { recovery = null; });
    return recovery;
  }
  async function request(path, options) {
    const originalToken = sessionStorage.getItem("access_token");
    let response;
    try { response = await fetch(path, options); }
    catch (_) {
      if (options.method && options.method !== "GET") {
        throw new Error("Connection lost. The save result is unknown. Check saved records before submitting again; your entries are kept.");
      }
      failed();
      throw new Error("Unable to load saved data. Check your connection and refresh saved data.");
    }
    if (response.status === 401 || (response.status === 403 && !originalToken)) {
      const restored = originalToken !== sessionStorage.getItem("access_token") || await reauthenticate();
      if (!restored) { failed(); throw new Error("Your entries are kept. Sign in when you are ready to continue."); }
      if (options.method && options.method !== "GET") {
        throw new Error("Session restored. Review your entries and submit again. The interrupted request was not retried.");
      }
      try {
        response = await fetch(path, {...options, headers: {...options.headers, Authorization: `Bearer ${sessionStorage.getItem("access_token")}`}});
      } catch (_) { failed(); throw new Error("Session restored, but saved data could not be loaded. Refresh saved data."); }
    }
    if (!response.ok && (!options.method || options.method === "GET")) failed();
    return response;
  }
  document.addEventListener("input", event => record(event.target));
  document.addEventListener("change", event => record(event.target));
  window.addEventListener("pagehide", persist);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && !recovery) refresh();
  });
  return {
    request, refresh, restore, record, discard, savedValue, afterSave,
    has: id => Object.hasOwn(state.fields, id),
    attach: hooks => { adapter = hooks; adapter.setSaleId?.(state.saleId); },
    saleCleared: () => { state.saleId = null; persist(); },
    select: section => { state.section = section; persist(); },
    initial: fallback => document.getElementById(`sec-${state.section}`) ? state.section : fallback,
    initialize: () => { restore(); adapter.afterRestore?.(); },
    forget: () => { remembering = false; sessionStorage.removeItem(key); },
  };
})();
