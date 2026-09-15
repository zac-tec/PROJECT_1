function addLabourGroup(group={workers:'',hours:''}){
 const row=document.createElement('div');row.className='labour-group';row.style.cssText='display:flex;gap:8px;align-items:end;flex-wrap:wrap';
 for(const [key,label,step] of [['workers','Workers','1'],['hours','Hours each','0.01']]){
  const wrap=document.createElement('label');wrap.textContent=label;wrap.style.flex='1';
  const input=document.createElement('input');input.type='number';input.min='0';input.step=step;input.value=group[key];input.dataset.labour=key;
  if(key==='hours')input.max='24';input.addEventListener('input',updateLabourTotals);wrap.append(input);row.append(wrap);
 }
 const button=document.createElement('button');button.type='button';button.className='secondary';button.textContent='Remove';button.onclick=()=>{row.remove();updateLabourTotals();};row.append(button);
 document.getElementById('labourGroupRows').append(row);updateLabourTotals();
}
function readLabourGroups(){
 if(document.getElementById('labourManualMode').checked)return null;
 return [...document.querySelectorAll('.labour-group')].map(row=>{
  const w=row.querySelector('[data-labour="workers"]'),h=row.querySelector('[data-labour="hours"]');
  if(w.value===''||h.value===''||!w.checkValidity()||!h.checkValidity())throw Error('Complete every worker/hour row, or remove unused rows.');
  return {workers:Number(w.value),hours:Number(h.value)};
 });
}
function updateLabourTotals(){
 const manual=document.getElementById('labourManualMode').checked;
 const rows=[...document.querySelectorAll('.labour-group')].map(row=>({workers:row.querySelector('[data-labour="workers"]').value,hours:row.querySelector('[data-labour="hours"]').value}));
 if(!manual){
  try{const groups=readLabourGroups();if(!groups.length)throw Error();
   document.getElementById('labourersInput').value=groups.reduce((v,g)=>v+g.workers,0);
   document.getElementById('labourHoursInput').value=(groups.reduce((v,g)=>v+g.workers*Math.round(g.hours*100),0)/100).toFixed(2);
  }catch(_){document.getElementById('labourersInput').value='';document.getElementById('labourHoursInput').value='';}
 }
 const hours=document.getElementById('labourHoursInput').value;
 document.getElementById('labourCostPreview').textContent=hours===''?'Complete the rows to calculate labour cost.':`${Number(hours)} working hours × ₹81.25 = ₹${(Math.round((Number(hours)*81.25+Number.EPSILON)*100)/100).toFixed(2)}`;
 const draft=document.getElementById('labourGroupsDraft');draft.value=JSON.stringify({manual,rows});draft.dispatchEvent(new Event('input',{bubbles:true}));
}
function setLabourMode(){
 const manual=document.getElementById('labourManualMode').checked;
 document.getElementById('labourGroupRows').hidden=manual;
 for(const id of ['labourersInput','labourHoursInput'])document.getElementById(id).readOnly=!manual;
 updateLabourTotals();
}
function restoreLabourGroups(){
 const raw=document.getElementById('labourGroupsDraft').value;
 if(!raw)return;
 try{const d=JSON.parse(raw);document.getElementById('labourManualMode').checked=d.manual;document.getElementById('labourGroupRows').replaceChildren();d.rows.forEach(addLabourGroup);setLabourMode();}catch(_){}
}
function resetLabourGroups(){document.getElementById('labourManualMode').checked=false;document.getElementById('labourGroupRows').replaceChildren();addLabourGroup();setLabourMode();}
for(const id of ['labourersInput','labourHoursInput'])document.getElementById(id).addEventListener('input',updateLabourTotals);
addLabourGroup();
