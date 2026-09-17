let saleCustomers=[];
window.saleAccountRequestId=()=>{
 let id=sessionStorage.getItem('sale-account-request');
 if(!id){id=crypto.randomUUID();sessionStorage.setItem('sale-account-request',id);}return id;
};
async function loadSaleCustomers(){
 const d=await apiFetch('/customer-accounts');saleCustomers=d.customers;
 const select=document.getElementById('saleCustomerAccount'),old=select.value;
 select.replaceChildren(new Option('New customer — enter name or phone',''));
 for(const c of saleCustomers)select.append(new Option(`${c.name||'Customer'}${c.phone?' · '+c.phone:''}`,c.customer_id));
 select.value=old;selectSaleCustomer();
}
function selectSaleCustomer(){
 const c=saleCustomers.find(c=>String(c.customer_id)===document.getElementById('saleCustomerAccount').value);
 const name=document.getElementById('saleCustomerName'),phone=document.getElementById('saleCustomerMobile');
 name.readOnly=phone.readOnly=!!c;
 const hint=document.getElementById('saleAccountBalance');
 if(c){name.value=c.name;phone.value=c.phone;const balance=Number(c.balance);hint.textContent=balance>0?'Customer owes '+money(balance):balance<0?'Customer credit: '+money(-balance):'Account fully settled';hint.className=balance>0?'financial-negative':balance<0?'financial-credit':'financial-positive';}
 else {hint.textContent='';hint.className='';}
}
window.resetSaleAccount=()=>{sessionStorage.removeItem('sale-account-request');document.getElementById('saleCustomerAccount').value='';selectSaleCustomer();};
loadSaleCustomers().catch(e=>showMessage(msgEl,e.message,true));
