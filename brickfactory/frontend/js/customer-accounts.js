(() => {
 let selected=null, requestId=crypto.randomUUID(), loadSequence=0;
 const message=document.getElementById('accountMessage');
 function el(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
 function state(value){return value>0?['Customer owes '+money(value),'financial-negative']:value<0?['Factory owes customer '+money(-value),'financial-credit']:['Fully settled','financial-positive'];}
 function date(value){return String(value).slice(0,10).split('-').reverse().join('-');}
 async function load(){
  const sequence=++loadSequence;
  const d=await apiFetch('/customer-accounts?q='+encodeURIComponent(document.getElementById('accountSearch').value)+'&include_archived='+document.getElementById('accountArchived').checked);
  if(sequence!==loadSequence)return;
  const filter=document.getElementById('accountFilter').value;
  d.customers=d.customers.filter(c=>filter==='all'||(filter==='owing'&&Number(c.balance)>0)||(filter==='credit'&&Number(c.balance)<0)||(filter==='settled'&&Number(c.balance)===0));
  const box=document.getElementById('accountList');box.replaceChildren();
  const table=el('table');const head=el('thead');head.append(el('tr'));['Customer','Phone','Account balance',''].forEach(v=>head.firstChild.append(el('th',v)));table.append(head);
  const body=el('tbody');table.append(body);
  for(const c of d.customers){const [label,cls]=state(Number(c.balance));const row=textRow(body,[(c.name||'(phone-only customer)')+(c.archived?' (archived)':''),c.phone||'—',label],[['View account','book-open',()=>open(c.customer_id)]]);row.children[2].className=cls;const button=row.lastElementChild.querySelector('button');button.className='secondary';button.textContent='Open account';}
  box.append(table);if(!d.customers.length)box.append(el('p','No customer accounts found.'));refreshIcons();
 }
 async function open(cid){
  if(!cid)return;if(selected!==cid)requestId=crypto.randomUUID();selected=cid;
  const d=await apiFetch('/customer-accounts/'+cid);render(d);if(Number(selected)===Number(cid))document.getElementById('accountDetail').scrollIntoView({behavior:'smooth',block:'start'});
 }
 function render(d){
  if(Number(d.customer.customer_id)!==Number(selected))return;
  const out=document.getElementById('accountDetail');out.classList.remove('hidden');out.replaceChildren();
  out.append(el('h2',d.customer.name||d.customer.phone),el('p',d.customer.phone||'No phone recorded'));
  const [label,cls]=state(Number(d.balance));out.append(el('h3',label,cls));
  if(d.customer.archived)out.append(el('p','Archived account — restore it before adding sales or changing transactions.'));
  const totals=el('div',undefined,'account-overview');
  for(const [name,value] of [['Purchases',d.invoices.length],['Total bricks',d.invoices.reduce((n,s)=>n+Number(s.bricks_purchased),0)],['Total billed',money(d.invoices.reduce((n,s)=>n+Number(s.total_amount),0))],['Applied to invoices',money(d.invoices.reduce((n,s)=>n+Number(s.amount_paid),0))]]){
    const card=el('div');card.append(el('small',name),el('strong',String(value)));totals.append(card);
  }
  out.append(totals);
  const toolbar=el('div',undefined,'account-actions');
  const print=el('button','Print / save statement');print.addEventListener('click',()=>printStatement(d));toolbar.append(print);
  const manage=el('button',d.customer.archived?'Restore customer':d.entries.length||d.invoices.length?'Archive customer':'Delete unused customer');
  manage.addEventListener('click',async()=>{
    const action=d.customer.archived?'restore':d.entries.length||d.invoices.length?'archive':'delete';
    if(!await confirmAction(action==='delete'?'Delete this unused customer account?':action==='archive'?'Archive this settled customer? Its history will remain available under Include archived customers.':'Restore this customer account?'))return;
    try{await apiFetch(`/customer-accounts/${selected}/manage`,{method:'POST',body:{action}});out.classList.add('hidden');selected=null;await load();message.textContent=action==='delete'?'Customer deleted.':action==='archive'?'Customer archived.':'Customer restored.';}
    catch(e){alert(e.message);}
  });toolbar.append(manage);out.append(toolbar);
  profileEditor(d,out);
  const form=el('form');const kind=el('select');
  for(const [value,label] of [['payment','Record payment received'],['refund','Refund customer credit'],['opening','Set complete current balance']]){const o=el('option',label);o.value=value;kind.append(o);}
  const direction=el('select');for(const [value,label] of [['1','Customer owes factory'],['-1','Factory owes customer']]){const o=el('option',label);o.value=value;direction.append(o);}direction.hidden=true;
  const amount=el('input');amount.type='number';amount.step='0.01';amount.min='0';amount.required=true;
  const note=el('input');note.required=true;note.minLength=3;note.maxLength=500;note.placeholder='Payment reference or reason';
  const status=el('p');status.setAttribute('role','status');
  const explanation=el('p','Payments clear the oldest unpaid amounts first. Extra money remains as customer credit.');
  const submit=el('button','Save transaction');submit.type='submit';
  function field(label,input){const wrap=el('label',label);wrap.append(input);return wrap;}
  form.append(field('Action',kind),direction,field('Amount (Rs.)',amount),field('Note / reference',note),explanation,submit,status);if(!d.customer.archived)out.append(form);
  kind.addEventListener('change',()=>{direction.hidden=kind.value!=='opening';explanation.textContent=kind.value==='opening'?'Enter the complete balance including saved invoices. Only the difference is recorded; use a negative direction for customer credit.':kind.value==='refund'?'Refunds are limited to the credit held for this customer.':'Payments clear the oldest unpaid amounts first. Extra money remains as credit.';});
  form.addEventListener('submit',async e=>{
   e.preventDefault();const amountValue=Number(amount.value)*(kind.value==='opening'?Number(direction.value):1);
   if(!Number.isFinite(amountValue))return;
   if(!await confirmAction(kind.value==='opening'?`Set the complete account balance to ${state(amountValue)[0]}?`:`Record ${money(Number(amount.value))} as ${kind.value}?`))return;
   try{const next=await apiFetch(`/customer-accounts/${selected}/entries`,{method:'POST',body:{kind:kind.value,amount:amountValue,note:note.value,request_id:requestId}});requestId=crypto.randomUUID();render(next);await load();await loadAllBrickSales();}
   catch(error){status.textContent=error.message;}
  });
  out.append(el('h3','Invoices — oldest first'));
  const table=el('table');const th=el('thead');th.append(el('tr'));['Date','Invoice','Bill incl. GST','Applied payments / credit','Outstanding',''].forEach(t=>th.firstChild.append(el('th',t)));table.append(th);const tb=el('tbody');table.append(tb);
  for(const s of d.invoices){const row=textRow(tb,[date(s.sale_date),'SR-'+String(s.sale_id).padStart(5,'0'),money(s.total_amount),money(s.amount_paid),Number(s.outstanding)>0?money(s.outstanding):'Fully paid'],[['Receipt','printer',()=>openReceipt(s.sale_id)]]);row.children[4].className=Number(s.outstanding)>0?'financial-negative':'financial-positive';}
  if(!d.invoices.length)out.append(el('p','No purchases recorded for this customer yet.'));
  const scroll=el('div',undefined,'table-scroll');scroll.append(table);out.append(scroll,el('h3','Account transactions — newest first'));
  const controls=el('div',undefined,'account-actions');const type=el('select');
  for(const [key,label] of [['all','All transactions'],['sale','Purchases'],['money','Payments and refunds'],['opening','Balance changes']]){const option=el('option',label);option.value=key;type.append(option);}
  const from=el('input');from.type='date';const to=el('input');to.type='date';
  controls.append(field('Type',type),field('From',from),field('To',to));out.append(controls);
  const history=el('table'),head=el('thead'),row=el('tr');['Date','Transaction','Debt / credit change','Running balance','Note',''].forEach(t=>row.append(el('th',t)));head.append(row);history.append(head);const ledger=el('tbody');history.append(ledger);
  const names={sale:'Sale',sale_payment:'Received with sale',import_payment:'Imported payment total',payment:'Payment received',refund:'Refund paid',opening:'Balance reconciliation',reversal:'Correction / reversal'};
  for(const entry of [...d.entries].reverse()){const [value,colour]=state(Number(entry.running_balance));const actions=[];
   if(!d.customer.archived && !entry.reversed && Number(entry.amount)!==0 && !['sale','reversal'].includes(entry.kind))actions.push(['Remove incorrect entry','undo-2',async()=>{
    const reason=prompt('Why are you removing this incorrect entry? (minimum 3 characters)');if(!reason||reason.trim().length<3)return;
    if(!await confirmAction('Remove this entry’s effect from the account? A correction record will remain, and invoice balances will be recalculated.'))return;
    try{const next=await apiFetch(`/customer-accounts/${selected}/entries/${entry.entry_id}/reverse`,{method:'POST',body:{note:reason,request_id:crypto.randomUUID()}});render(next);await load();await loadAllBrickSales();}catch(e){message.textContent=e.message;}
   }]);
   const r=textRow(ledger,[date(entry.effective_date),names[entry.kind]+(entry.reversed?' (removed)':''),(Number(entry.amount)>=0?'+':'−')+money(Math.abs(Number(entry.amount))),value,entry.note],actions);r.children[3].className=colour;r.dataset.kind=entry.kind;r.dataset.date=entry.effective_date;
   if(entry.reversed)r.classList.add('account-removed');
   const remove=r.querySelector('button');if(remove){remove.className='secondary';remove.textContent='Remove entry';}
   if(entry.kind==='sale')r.children[1].textContent+=' · SR-'+String(entry.sale_id).padStart(5,'0');
  }
  const wrap=el('div',undefined,'table-scroll');wrap.append(history);out.append(wrap);
  const filterRows=()=>{for(const row of ledger.rows){const k=row.dataset.kind;row.hidden=(from.value&&row.dataset.date<from.value)||(to.value&&row.dataset.date>to.value)||(type.value==='sale'&&k!=='sale')||(type.value==='money'&&!['payment','sale_payment','import_payment','refund'].includes(k))||(type.value==='opening'&&!['opening','reversal'].includes(k));}};
  [type,from,to].forEach(input=>input.addEventListener('change',filterRows));
  out.append(el('p','Balances cover the whole account. Filters only change the rows shown. Remove entry reverses an incorrect money/balance entry; purchases remain linked to their original invoices.'));
  refreshIcons();
 }

 function profileEditor(d,out){
  const section=el('details');section.append(el('summary','Contact details, notes and edit profile'));
  const form=el('form');const inputs={};
  for(const [key,label] of [['name','Name'],['phone','Phone'],['address','Address'],['notes','Notes']]){
   const wrap=el('label',label),input=el(['address','notes'].includes(key)?'textarea':'input');input.value=d.customer[key]||'';input.maxLength={name:100,phone:30,address:1000,notes:2000}[key];inputs[key]=input;wrap.append(input);form.append(wrap);
  }
  const save=el('button','Save customer details');save.type='submit';const status=el('p');form.append(save,status);section.append(form);out.append(section);
  form.addEventListener('submit',async e=>{e.preventDefault();try{const body=Object.fromEntries(Object.entries(inputs).map(([k,v])=>[k,v.value]));const updated=await apiFetch(`/customer-accounts/${selected}/profile`,{method:'PUT',body});render(updated);await load();}catch(error){status.textContent=error.message;}});
 }
 function printStatement(d){
  const w=window.open('','_blank');if(!w){alert('Allow popups to print the customer statement.');return;}
  w.opener=null;w.document.title='NEO BRICKS — Customer statement';const body=w.document.body;body.replaceChildren();
  const style=el('style','body{font:14px Arial,sans-serif;color:#222;margin:28px}table{border-collapse:collapse;width:100%;margin:18px 0;font-size:12px}td,th{padding:7px;border:1px solid #ccc;text-align:left}thead{display:table-header-group}tr{break-inside:avoid}h1{font-size:22px}@media print{button{display:none}}');w.document.head.append(style);
  body.append(el('h1','NEO BRICKS — Customer statement'),el('h2',d.customer.name||d.customer.phone),el('p',d.customer.phone||''),el('p',d.customer.address||''),el('p',state(Number(d.balance))[0]));
  body.append(el('p','Generated '+new Date().toLocaleDateString('en-GB',{timeZone:'Asia/Kolkata'})));
  const table=el('table'),head=el('thead'),hr=el('tr');['Date','Entry','Change (Rs.)','Balance','Note'].forEach(v=>hr.append(el('th',v)));head.append(hr);table.append(head);const tbody=el('tbody');table.append(tbody);
  for(const e of d.entries)textRow(tbody,[date(e.effective_date),({sale:'Sale',sale_payment:'Payment with sale',import_payment:'Imported payment',payment:'Payment received',refund:'Refund',opening:'Balance reconciliation',reversal:'Correction'}[e.kind]||e.kind)+(e.sale_id?' · SR-'+String(e.sale_id).padStart(5,'0'):'')+(e.reversed?' (removed)':''),Number(e.amount).toFixed(2),state(Number(e.running_balance))[0],e.note]);
  body.append(table,el('p','Positive changes increase what the customer owes; negative changes reduce it. Removed entries remain visible with their correcting reversal.'));
  const print=el('button','Print / save as PDF');print.addEventListener('click',()=>w.print());body.append(print);w.focus();
 }
 window.openCustomerAccount=async cid=>{activateSection('customerAccounts');try{await open(cid);}catch(e){message.textContent=e.message;}};
 document.getElementById('createAccount').addEventListener('click',async()=>{
  try{const c=await apiFetch('/customer-accounts',{method:'POST',body:{name:document.getElementById('newAccountName').value,phone:document.getElementById('newAccountPhone').value}});await load();await open(c.customer_id);message.textContent='Account opened. Set its complete balance below if needed.';}catch(e){message.textContent=e.message;}
 });
 ['accountFilter','accountArchived'].forEach(id=>document.getElementById(id).addEventListener('change',()=>load().catch(e=>message.textContent=e.message)));
 document.getElementById('accountRefresh').addEventListener('click',()=>load().catch(e=>message.textContent=e.message));
 let timer;document.getElementById('accountSearch').addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(()=>load().catch(e=>message.textContent=e.message),250);});
 onSectionLoad('customerAccounts',()=>Promise.all([load(),loadAllBrickSales(),loadMonthlySalesSummary()]));
 if(!document.getElementById('sec-customerAccounts').classList.contains('hidden'))load().catch(e=>message.textContent=e.message);
})();
