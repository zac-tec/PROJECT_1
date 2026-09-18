// Keep existing tables, edit controls and event handlers; add readable phone labels.
(() => {
  const main = document.querySelector('main.content');
  if (!main) return;
  function adaptTables() {
    for (const table of main.querySelectorAll('table')) {
      const headers = table.tHead?.rows;
      if (headers?.length === 1 && [...headers[0].cells].every(c => c.colSpan === 1)) {
        table.classList.add('responsive-records');
        const labels = [...headers[0].cells].map(c => c.textContent.trim());
        for (const body of table.tBodies) for (const row of body.rows) {
          for (const [i, cell] of [...row.cells].entries()) {
            cell.dataset.label = labels[i] || 'Actions';
            cell.classList.toggle('record-wide',cell.colSpan > 1);
          }
        }
      }
      if (!table.parentElement.classList.contains('table-scroll')) {
        const wrap = document.createElement('div');
        wrap.className = 'table-scroll';
        table.before(wrap); wrap.append(table);
      }
    }
    // Existing labels become clickable without changing any input IDs.
    for (const label of main.querySelectorAll('label:not([for])')) {
      const input = label.nextElementSibling;
      if (input?.matches('input[id],select[id],textarea[id]')) label.htmlFor = input.id;
    }
  }
  let queued = false;
  new MutationObserver(() => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; adaptTables(); });
  }).observe(main, {childList:true,subtree:true});
  adaptTables();
})();
