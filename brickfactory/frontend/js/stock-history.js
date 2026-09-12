async function loadStockHistory() {
  const out=document.getElementById('stockHistoryOutput'); out.textContent='Loading…';
  try {
    const data=await apiFetch('/admin/stock-history?month='+encodeURIComponent(document.getElementById('historyMonth').value));
    out.replaceChildren();
    function paragraph(text){const p=document.createElement('p');p.textContent=text;out.append(p);}
    function table(headers,rows){const t=document.createElement('table');const head=document.createElement('tr');headers.forEach(h=>{const th=document.createElement('th');th.textContent=h;head.append(th);});t.append(head);rows.forEach(row=>{const tr=document.createElement('tr');row.forEach(v=>{const td=document.createElement('td');td.textContent=v==null?'—':String(v);tr.append(td);});t.append(tr);});out.append(t);}
    paragraph(data.note);
    data.imports.forEach(i=>paragraph('Confirmed stock at '+i.cutover_date+': '+i.confirmed_closing.toLocaleString()+' bricks. '+i.notes));
    if(data.complete_month_ledger) paragraph('Month opening: '+data.opening.toLocaleString()+' · Closing to latest entry: '+data.closing.toLocaleString());
    paragraph('Handwritten stock ledger — as written; repeated dates and differences retained');
    const stock=data.rows.filter(r=>r.page===1||r.page===2);
    table(['Date','Page / row','Opening','Outward / sale','Production','Closing','Notes'],stock.map(r=>[r.entry_date,r.page+' / '+r.row_number,r.data.Opening,r.data.Sale,r.data.Production,r.data.Closing,r.data.Notes]));
    paragraph('Other historical registers — units and corrections require review; not added to material stock');
    table(['Date','Page / row','Source values'],data.rows.filter(r=>r.page>2).map(r=>[r.entry_date,r.page+' / '+r.row_number,Object.entries(r.data).map(([k,v])=>k+': '+v).join(' | ')]));
    paragraph('Recorded finished-stock movements (initial import is a reconciled snapshot)');
    table(['Date','Batch','Change','Reason'],data.movements.map(m=>[m.date,m.batch_id,m.quantity,m.reason]));
    if(!data.rows.length&&!data.movements.length)paragraph('No records for this month.');
  }catch(e){out.textContent=e.message||'Unable to load stock history.';}
}
