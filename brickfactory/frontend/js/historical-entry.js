let historyRevision=0,historyStatus='draft';
function hnode(tag,text){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e;}
function historyRow(row={date:'',mixes:0,bricks:0,sales:[]}){
 const tr=hnode('tr');
 for(const [type,value] of [['date',row.date],['number',row.mixes],['number',row.bricks],['text',row.sales.join(', ')]]){
  const td=hnode('td'),input=document.createElement('input');input.type=type;input.value=value;
  if(type==='number'){input.min='0';input.step='1';}if(type==='text')input.placeholder='2500, 1000, 2500';td.append(input);tr.append(td);
 }
 const td=hnode('td'),btn=hnode('button','Remove');btn.type='button';btn.onclick=()=>tr.remove();td.append(btn);tr.append(td);document.getElementById('historyEntryRows').append(tr);
}
function parseHistoryRows(rows){
 return rows.flatMap((values,index)=>{
  const [date,mix,brick,sale]=values;const raw=sale.trim();
  if(!date && !Number(mix) && !Number(brick) && (!raw || /^0+(\s*,\s*0+)*$/.test(raw)))return [];
  if(!date)throw Error(`Row ${index+1}: enter a date or remove this row.`);
  if(raw&&!/^\d+(\s*,\s*\d+)*$/.test(raw))throw Error(`Row ${index+1}: use whole sale quantities separated by commas, e.g. 2500, 1000. Enter 0 or leave blank for no sales.`);
  const mixes=Number(mix),bricks=Number(brick);
  if(!Number.isSafeInteger(mixes)||mixes<0||!Number.isSafeInteger(bricks)||bricks<0)throw Error(`Row ${index+1}: mixes and production must be nonnegative whole numbers.`);
  return [{date,mixes,bricks,sales:raw?raw.split(',').map(Number).filter(q=>q>0):[]}];
 });
}
function historyFeedback(text,error=false){
 for(const id of ['historyEntryMessage','historyEntryBottomMessage']){const e=document.getElementById(id);if(e){e.textContent=text;e.style.color=error?'#b42318':'';e.setAttribute('role',error?'alert':'status');}}
}
function historyFailed(e){document.getElementById('historyEntryPreview').replaceChildren();historyFeedback(e.message||'Unable to complete this operation.',true);}
function readHistoryDraft(){
 const days=parseHistoryRows([...document.querySelectorAll('#historyEntryRows tr')].map(tr=>[...tr.querySelectorAll('input')].map(i=>i.value)));
 const recipe={};document.querySelectorAll('[data-history-material]').forEach(i=>recipe[i.dataset.historyMaterial]=Number(i.value));
 return {revision:historyRevision,start_date:document.getElementById('historyStart').value,end_date:document.getElementById('historyEnd').value,opening_bricks:Number(document.getElementById('historyOpening').value),opening_confirmed_cured:document.getElementById('historyOpeningCured').checked,recipe,recipe_note:document.getElementById('historyRecipeNote').value,days};
}
function historyResult(data){
 const out=document.getElementById('historyEntryPreview');out.replaceChildren();
 const totals=data.totals;
 out.append(hnode('p',`As of ${data.as_of}: total ${totals.total.toLocaleString()} · under 7 days ${totals.curing.toLocaleString()} · 7–13 days ${totals.early_sale.toLocaleString()} · 14+ days ${totals.fully_cured.toLocaleString()} · saleable ${totals.saleable.toLocaleString()}`));
 out.append(hnode('p','Estimated material consumption: '+Object.entries(data.materials).map(([k,v])=>`${k}: ${v.toLocaleString()} ${k==='Chemical'?'L':k==='Cement'?'bags':'kg'}`).join(' · ')));
 const t=hnode('table'),head=hnode('tr');['Date','Opening','Mixes','Produced','Sales','Closing','Estimated material usage'].forEach(v=>head.append(hnode('th',v)));t.append(head);
 data.days.forEach(r=>{const tr=hnode('tr');[r.date,r.opening,r.mixes,r.production,r.sales,r.closing,Object.entries(r.materials).map(([k,v])=>k+': '+v).join(' · ')].forEach(v=>tr.append(hnode('td',v)));t.append(tr);});out.append(t);
}
async function loadHistoricalEntry(){
 const msg=document.getElementById('historyEntryMessage');
 try{
  const data=await apiFetch('/admin/historical-entry');const s=data.session;historyRevision=s?s.revision:0;historyStatus=s?s.status:'draft';
  const p=s?s.payload:{start_date:'2026-08-19',end_date:data.today,opening_bricks:81135,recipe:data.recipe,recipe_note:'Current recipe estimate; verify for the historical period.',days:[],opening_confirmed_cured:true};
  document.getElementById('historyStart').value=p.start_date;document.getElementById('historyEnd').value=p.end_date;document.getElementById('historyOpening').value=p.opening_bricks;document.getElementById('historyOpeningCured').checked=p.opening_confirmed_cured;document.getElementById('historyRecipeNote').value=p.recipe_note;
  const recipes=document.getElementById('historyRecipeFields');recipes.replaceChildren();
  Object.entries(p.recipe).forEach(([k,v])=>{const label=hnode('label',`${k} per mix (${k==='Chemical'?'L':k==='Cement'?'bags':'kg'})`);const input=document.createElement('input');input.type='number';input.min='0';input.step='0.001';input.value=v;input.dataset.historyMaterial=k;label.append(input);recipes.append(label);});
  document.getElementById('historyEntryRows').replaceChildren();p.days.forEach(historyRow);
  document.querySelectorAll('#historyEntryEditor input,#historyEntryEditor button,#historyEntryEditor textarea').forEach(e=>e.disabled=historyStatus==='applied');
  msg.textContent=historyStatus==='applied'?'History applied. This one-time session is locked; view its saved preview below.':'Draft saved on server. Edit rows, save, then preview before applying.';
  if(p.days.length)historyResult(await apiFetch('/admin/historical-entry/preview',{method:'POST',body:{...p,revision:historyRevision}}));
 }catch(e){msg.textContent=e.message;}
}
async function saveHistoricalEntry(){try{const body=readHistoryDraft();const r=await apiFetch('/admin/historical-entry/save',{method:'POST',body});historyRevision=r.revision;historyFeedback(`Saved ${body.days.length} dated rows to the database. Live stock has not changed.`);document.getElementById('historyEntryPreview').replaceChildren();}catch(e){historyFailed(e);}}
async function previewHistoricalEntry(){try{historyResult(await apiFetch('/admin/historical-entry/preview',{method:'POST',body:readHistoryDraft()}));}catch(e){historyFailed(e);}}
async function applyHistoricalEntry(){
 try{
  const body=readHistoryDraft();const result=await apiFetch('/admin/historical-entry/preview',{method:'POST',body});historyResult(result);
  if(!confirm(`Apply this saved historical draft as the starting stock of ${result.totals.total} bricks? It will lock this session. Historical material usage is an estimate and will NOT deduct from current material stock. Customer invoices and financial reports will not be invented.`))return;
  await apiFetch('/admin/historical-entry/apply',{method:'POST',body});await loadHistoricalEntry();
 }catch(e){historyFailed(e);}
}
