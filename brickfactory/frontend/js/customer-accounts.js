(() => {
 let selected=null, requestId=crypto.randomUUID();
 const message=document.getElementById('accountMessage');
 function el(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
 function state(value){return value>0?['Customer owes '+money(value),'financial-negative']:value<0?['Factory owes customer '+money(-value),'financial-credit']:['Fully settled','financial-positive'];}
 function date(value){return String(value).slice(0,10).split('-').reverse().join('-');}
 async function load(){
  const d=await apiFetch('/customer-accounts?q='+encodeURIComponent(document.getElementById('accountSearch').value));
  const box=document.getElementById('accountList');box.replaceChildren();
  const table=el('table');const head=el('thead');head.append(el('tr'));['Customer','Phone','Account balance',''].forEach(v=>head.firstChild.append(el('th',v)));table.append(head);
  const body=el('tbody');table.append(body);
  for(const c of d.customers){const [label,cls]=state(Number(c.balance));const row=textRow(body,[c.name||'(phone-only customer)',c.phone||'—',label],[['View account','book-open',()=>open(c.customer_id)]]);row.children[2].className=cls;}
  box.append(table);if(!d.customers.length)box.append(el('p','No customer accounts found.'));refreshIcons();
 }
 async function open(cid){
  if(!cid)return;if(selected!==cid)requestId=crypto.randomUUID();selected=cid;
  const d=await apiFetch('/customer-accounts/'+cid);render(d);
 }
 function render(d){
  if(Number(d.customer.customer_id)!==Number(selected))return;
  const out=document.getElementById('accountDetail');out.classList.remove('hidden');out.replaceChildren();
  out.append(el('h2',d.customer.name||d.customer.phone),el('p',d.customer.phone||'No phone recorded'));
  const [label,cls]=state(Number(d.balance));out.append(el('h3',label,cls));
  const form=el('form');const kind=el('select');
  for(const [value,label] of [['payment','Record payment received'],['refund','Refund customer credit'],['opening','Set complete current balance']]){const o=el('option',label);o.value=value;kind.append(o);}
  const direction=el('select');for(const [value,label] of [['1','Customer owes factory'],['-1','Factory owes customer']]){const o=el('option',label);o.value=value;direction.append(o);}direction.hidden=true;
  const amount=el('input');amount.type='number';amount.step='0.01';amount.min='0';amount.required=true;
  const note=el('input');note.required=true;note.minLength=3;note.maxLength=500;note.placeholder='Payment reference or reason';
  const status=el('p');status.setAttribute('role','status');
  const explanation=el('p','Payments clear the oldest unpaid amounts first. Extra money remains as customer credit.');
  const submit=el('button','Save transaction');submit.type='submit';
  function field(label,input){const wrap=el('label',label);wrap.append(input);return wrap;}
  form.append(field('Action',kind),direction,field('Amount (Rs.)',amount),field('Note / reference',note),explanation,submit,status);out.append(form);
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
  const scroll=el('div',undefined,'table-scroll');scroll.append(table);out.append(scroll,el('h3','Account transactions'));
  const history=el('table'),head=el('thead'),row=el('tr');['Date','Transaction','Debt / credit change','Running balance','Note',''].forEach(t=>row.append(el('th',t)));head.append(row);history.append(head);const ledger=el('tbody');history.append(ledger);
  const names={sale:'Sale',sale_payment:'Received with sale',import_payment:'Imported payment total',payment:'Payment received',refund:'Refund paid',opening:'Balance reconciliation',reversal:'Correction / reversal'};
  for(const entry of d.entries){const [value,colour]=state(Number(entry.running_balance));const actions=[];
   if(!entry.reversed && !['sale','reversal'].includes(entry.kind))actions.push(['Reverse incorrect entry','undo-2',async()=>{
    const reason=prompt('Reason for reversing this entry (minimum 3 characters):');if(!reason||reason.trim().length<3)return;
    if(!await confirmAction('Reverse this account entry and recalculate invoice balances?'))return;
    try{const next=await apiFetch(`/customer-accounts/${selected}/entries/${entry.entry_id}/reverse`,{method:'POST',body:{note:reason,request_id:crypto.randomUUID()}});render(next);await load();await loadAllBrickSales();}catch(e){message.textContent=e.message;}
   }]);
   const r=textRow(ledger,[date(entry.effective_date),names[entry.kind]+(entry.reversed?' (reversed)':''),(Number(entry.amount)>=0?'+':'−')+money(Math.abs(Number(entry.amount))),value,entry.note],actions);r.children[3].className=colour;
  }
  const wrap=el('div',undefined,'table-scroll');wrap.append(history);out.append(wrap);refreshIcons();
 }
 window.openCustomerAccount=async cid=>{activateSection('customerAccounts');try{await open(cid);}catch(e){message.textContent=e.message;}};
 document.getElementById('createAccount').addEventListener('click',async()=>{
  try{const c=await apiFetch('/customer-accounts',{method:'POST',body:{name:document.getElementById('newAccountName').value,phone:document.getElementById('newAccountPhone').value}});await load();await open(c.customer_id);message.textContent='Account opened. Set its complete balance below if needed.';}catch(e){message.textContent=e.message;}
 });
 document.getElementById('accountRefresh').addEventListener('click',()=>load().catch(e=>message.textContent=e.message));
 let timer;document.getElementById('accountSearch').addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(()=>load().catch(e=>message.textContent=e.message),250);});
 onSectionLoad('customerAccounts',()=>Promise.all([load(),loadAllBrickSales(),loadMonthlySalesSummary()]));
 if(!document.getElementById('sec-customerAccounts').classList.contains('hidden'))load().catch(e=>message.textContent=e.message);
})();
