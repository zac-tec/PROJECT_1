/* Visible app presence; one account is counted once across devices/tabs. */
(() => {
  const output = document.getElementById("activeUsersOutput");
  const count = document.getElementById("activeUsersCount");
  let busy = false;

  async function update() {
    const token = sessionStorage.getItem("access_token");
    if (busy || document.visibilityState !== "visible" || !token) return;
    busy = true;
    const headers = { Authorization: `Bearer ${token}` };
    try {
      const beat = await fetch("/presence/heartbeat", {
        method: "POST", headers, cache: "no-store", signal: AbortSignal.timeout(10000)
      });
      if (!beat.ok) throw new Error("Presence unavailable");
      if (!output) return;
      const result = await fetch("/presence/active", {
        headers, cache: "no-store", signal: AbortSignal.timeout(10000)
      });
      if (!result.ok) throw new Error("Presence unavailable");
      const data = await result.json();
      count.textContent = String(data.count);
      const table = document.createElement("table");
      const head = table.createTHead().insertRow();
      for (const title of ["User", "Role", "Last seen (IST)"]) {
        const cell = document.createElement("th");
        cell.textContent = title;
        head.appendChild(cell);
      }
      const body = table.createTBody();
      for (const user of data.users) {
        const row = body.insertRow();
        for (const value of [user.username, user.role,
          new Date(user.last_seen).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })]) {
          row.insertCell().textContent = value;
        }
      }
      output.replaceChildren(table);
    } catch (_) {
      if (output) {
        count.textContent = "—";
        output.textContent = "Unable to refresh active users. Retrying automatically.";
      }
    } finally { busy = false; }
  }
  document.getElementById("refreshActiveUsers")?.addEventListener("click", update);
  document.addEventListener("visibilitychange", update);
  window.addEventListener("online", update);
  update();
  setInterval(update, 60000);
})();
