(() => {
  const field = document.getElementById('productionBackdateDays');
  const status = document.getElementById('productionWindowStatus');
  if (field) {
    apiFetch('/production-entry/settings').then(d => {field.value = d.backdate_days;})
      .catch(e => {status.textContent = e.message;});
    document.getElementById('saveProductionWindow').addEventListener('click', async () => {
      try {
        const days = Number(field.value);
        if (field.value === '' || !Number.isInteger(days) || days < 0 || days > 3650) throw new Error('Enter a whole number from 0 to 3650.');
        const d = await apiFetch('/admin/production-entry/settings', {method:'PUT',body:{backdate_days:days}});
        status.textContent = `Saved: ${d.backdate_days} previous day(s), plus today, for production and sales.`;
      } catch(e) {status.textContent = e.message;}
    });
  }
  const dialog = document.createElement('dialog');
  const message = document.createElement('p');
  const button = document.createElement('button');
  button.textContent = 'OK'; button.addEventListener('click', () => dialog.close());
  dialog.append(message,button); document.body.append(dialog);
  let checked = false;
  async function checkReminder() {
    if (document.hidden || checked) return;
    checked = true;
    try {
      // Do not interrupt with a reauthentication prompt just to check a reminder.
      const token=sessionStorage.getItem('access_token');
      if (!token) return;
      const response=await fetch('/production-entry/reminder',{headers:{Authorization:`Bearer ${token}`},cache:'no-store'});
      if (!response.ok) return;
      const d=await response.json();
      if (!d.show) {if (dialog.open) dialog.close(); return;}
      const key=`production-reminder:${sessionStorage.getItem('username')}:${d.date}`;
      if (sessionStorage.getItem(key)) return;
      message.textContent=d.message;
      // Avoid competing with an existing form confirmation or session dialog.
      if (document.querySelector('dialog[open]')) return;
      dialog.showModal(); sessionStorage.setItem(key,'shown');
    } catch (_) { /* A reminder failure must never prevent data entry. */ }
    finally {checked=false;}
  }
  checkReminder();
  setInterval(checkReminder,60000);
  document.addEventListener('visibilitychange',checkReminder);
})();
