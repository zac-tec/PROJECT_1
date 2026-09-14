async function loadHistoricalLabour(){
 const out=document.getElementById('historicalLabourRows');
 try{const d=await apiFetch('/admin/historical-labour');const table=document.createElement('table');
 table.innerHTML='<thead><tr><th>Date</th><th>Bricks produced</th><th>Total person-hours</th></tr></thead><tbody></tbody>';
 for(const day of d.days){const tr=document.createElement('tr');
 for(const value of [displayDate(day.date),day.bricks]){const td=document.createElement('td');td.textContent=value;tr.append(td);}
 const td=document.createElement('td'),input=document.createElement('input');input.type='number';input.min='0';input.step='0.01';input.placeholder='Unknown';input.value=day.hours??'';input.dataset.date=day.date;input.dataset.revision=day.revision;input.dataset.original=input.value;td.append(input);tr.append(td);table.querySelector('tbody').append(tr);}
 out.replaceChildren(table);
 }catch(e){document.getElementById('historicalLabourMessage').textContent=e.message;}
}
async function saveHistoricalLabour(){
 const msg=document.getElementById('historicalLabourMessage');
 try{const days=[...document.querySelectorAll('#historicalLabourRows input')].filter(i=>i.value!==''&&i.value!==i.dataset.original).map(i=>{if(!i.checkValidity())throw Error('Enter valid nonnegative hours.');return {date:i.dataset.date,hours:Number(i.value),revision:Number(i.dataset.revision)};});
 if(!days.length){msg.textContent='Enter or change hours before saving.';return;}
 const r=await apiFetch('/admin/historical-labour',{method:'POST',body:{days}});msg.textContent=`Saved ${r.saved} dates. Labour costs updated; stock unchanged.`;await loadHistoricalLabour();await loadProductionCosts();
 }catch(e){msg.textContent=e.message;}
}

loadHistoricalLabour();
