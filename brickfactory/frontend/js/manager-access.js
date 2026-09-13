async function loadManagerAccess(){
 const msg=document.getElementById('managerAccessMessage');
 try{
  const d=await apiFetch('/admin/manager-access');
  const select=document.getElementById('accessManager');select.replaceChildren();
  for(const manager of d.managers){const option=document.createElement('option');option.value=manager.username;option.textContent=manager.username;select.append(option);}
  const out=document.getElementById('managerAccessAudit');out.replaceChildren();
  for(const a of d.audit){const row=document.createElement('p');row.textContent=`${new Date(a.changed_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})}: ${a.previous_username} → ${a.new_username}; by ${a.changed_by}. Reason: ${a.reason}`;out.append(row);}
 }catch(e){msg.textContent=e.message;}
}
document.getElementById('managerAccessForm').addEventListener('submit',async e=>{
 e.preventDefault();const msg=document.getElementById('managerAccessMessage');
 const password=document.getElementById('accessPassword'),confirmation=document.getElementById('accessConfirm');
 if(password.value!==confirmation.value){msg.textContent='Passwords do not match.';return;}
 const body={current_username:document.getElementById('accessManager').value,new_username:document.getElementById('accessUsername').value.trim(),new_password:password.value,reason:document.getElementById('accessReason').value.trim()};
 try{
  const d=await apiFetch('/admin/manager-access',{method:'POST',body});
  msg.textContent=d.message;document.getElementById('managerAccessForm').reset();
  if(typeof sessionUI!=='undefined')sessionUI.discard(['accessManager','accessUsername','accessReason']);
  await loadManagerAccess();
 }catch(err){msg.textContent=err.message;}
 finally{password.value='';confirmation.value='';body.new_password='';}
});
loadManagerAccess();
