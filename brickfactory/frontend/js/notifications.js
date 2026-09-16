/* Each installed device opts in separately. Closing the app keeps reminders enabled. */
(() => {
  const panel = document.getElementById('pushSettings');
  if (!panel) return;
  const status = panel.querySelector('[data-push-status]');
  const enable = panel.querySelector('[data-push-enable]');
  const disable = panel.querySelector('[data-push-disable]');
  const supported = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  function keyBytes(key) {
    const raw = atob(key.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - key.length % 4) % 4));
    return Uint8Array.from(raw, c => c.charCodeAt(0));
  }
  async function registration() {
    await navigator.serviceWorker.register('sw.js');
    return navigator.serviceWorker.ready;
  }
  async function refresh() {
    if (!supported) {
      status.textContent = 'Push notifications are unavailable here. On iPhone, open the installed Home Screen app.';
      enable.disabled = disable.disabled = true;
      return;
    }
    try {
      const sub = await (await registration()).pushManager.getSubscription();
      if (sub && Notification.permission === 'granted') {
        // Rebind on login so a shared phone never stays assigned to a previous account.
        await apiFetch('/notifications/subscribe', {method: 'POST', body: sub.toJSON()});
      }
      status.textContent = sub ? 'Notifications enabled on this device.' : 'Notifications are off on this device.';
      disable.hidden = !sub;
      enable.hidden = !!sub;
    } catch (e) { status.textContent = e.message; }
  }
  enable.addEventListener('click', async () => {
    try {
      // Request directly from the user gesture (required on mobile browsers).
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') throw new Error('Allow notifications in your phone/browser settings, then try again.');
      const config = await apiFetch('/notifications/config');
      if (!config.enabled) throw new Error('Notifications are not configured yet.');
      const sub = await (await registration()).pushManager.subscribe({userVisibleOnly: true, applicationServerKey: keyBytes(config.public_key)});
      await apiFetch('/notifications/subscribe', {method: 'POST', body: sub.toJSON()});
      await refresh();
    } catch (e) { status.textContent = e.message; }
  });
  async function turnOff() {
    if (!supported) return;
    const sub = await (await registration()).pushManager.getSubscription();
    if (sub) {
      await apiFetch('/notifications/unsubscribe', {method: 'POST', body: {endpoint: sub.endpoint}});
      await sub.unsubscribe();
    }
  }
  window.disableDeviceNotifications = turnOff;
  disable.addEventListener('click', async () => {
    try { await turnOff(); await refresh(); } catch (e) { status.textContent = e.message; }
  });
  refresh();
})();
