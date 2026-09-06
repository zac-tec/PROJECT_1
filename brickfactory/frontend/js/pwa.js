/*
  PWA install handling. Purely additive — registers the service worker
  and wires up the "Install App" button. Safe to remove this file entirely
  and the rest of the app keeps working exactly as before.
*/
(function () {
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("sw.js").catch(() => {});
    });
  }

  let deferredPrompt = null;

  function getInstallBtn() {
    return document.getElementById("installBtn");
  }

  // Chrome/Edge/Android fire this when the app meets install criteria
  // (manifest + service worker + served over HTTPS or localhost).
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredPrompt = e;
    const btn = getInstallBtn();
    if (btn) btn.classList.remove("hidden");
  });

  window.addEventListener("appinstalled", () => {
    deferredPrompt = null;
    const btn = getInstallBtn();
    if (btn) btn.classList.add("hidden");
  });

  document.addEventListener("DOMContentLoaded", () => {
    const btn = getInstallBtn();
    if (!btn) return;

    // Already running as an installed app — nothing to offer.
    const isStandalone =
      window.matchMedia("(display-mode: standalone)").matches ||
      window.navigator.standalone === true;
    if (isStandalone) {
      btn.classList.add("hidden");
      return;
    }

    btn.addEventListener("click", async () => {
      if (!deferredPrompt) return;
      deferredPrompt.prompt();
      await deferredPrompt.userChoice;
      deferredPrompt = null;
      btn.classList.add("hidden");
    });
  });
})();
