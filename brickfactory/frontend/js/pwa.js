/*
  PWA support. Purely additive — registers the service worker and leaves
  installation to the browser's native Chrome/Edge controls. Safe to remove this file entirely
  and the rest of the app keeps working exactly as before.
*/
(function () {
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("sw.js").catch(() => {});
    });
  }

})();
