// Focused regression: a slow preview must never overwrite a newer input.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../frontend/js/manager-security1.js'), 'utf8');
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {value:'',textContent:'',style:{},classList:{add(){},remove(){}},checkValidity(){return true;},replaceChildren(){},append(){}});
  return elements.get(id);
}
for (const [id,value] of Object.entries({salePricingMode:'delivered_base',saleBricksPurchased:'2500',saleCostPerBrick:'8.17',saleOtherCharges:'0',saleTransportMode:'flat',saleTransportRate:'2200',saleAmountPaid:'0'})) element(id).value=value;
const pending=[];
const context=vm.createContext({document:{getElementById:element,createElement:()=>({style:{}})},setTimeout,clearTimeout,Number,JSON,saleSaving:false,editingSaleId:null,money:n=>Number(n).toFixed(2),apiFetch:(path,options)=>new Promise((resolve,reject)=>pending.push({path,options,resolve,reject}))});
vm.runInContext(source.slice(source.indexOf('let salePreviewTimer;'),source.indexOf('function clearSaleForm()')),context);
const wait=()=>new Promise(resolve=>setTimeout(resolve,210));
(async()=>{
 vm.runInContext('recalculateSale()',context);await wait();
 assert.equal(pending[0].options.busy,false);
 assert.equal(pending[0].options.body.cost_per_brick,'8.17');
 element('saleCostPerBrick').value='8.18';
 vm.runInContext('recalculateSale()',context);await wait();
 const values={total_amount:22904,amount_due:20440,taxable_amount:20450,transport_base_amount:2200,brick_base_amount:18250,other_base_amount:0,base_unit_price:7.3,transport_per_brick:.88,delivered_base_price:8.18,gst_amount:2454,brick_gst:2190,transport_gst:264,other_gst:0};
 pending[1].resolve(values);await wait();
 assert.equal(element('saleTotalAmount').textContent,'22904.00');
 assert.equal(element('saleSubmitBtn').disabled,false);
 pending[0].resolve({...values,total_amount:22876});await wait();
 assert.equal(element('saleTotalAmount').textContent,'22904.00');
 element('saleCostPerBrick').value='0.01';
 vm.runInContext('recalculateSale()',context);await wait();
 pending[2].reject(new Error('The delivered amount must be greater than the driver charge.'));await wait();
 assert.equal(element('saleSubmitBtn').disabled,true);
 assert.match(element('salePricingStatus').textContent,/driver charge/);
 console.log('PASS: live preview, current input, stale-response protection and invalid-price save blocking.');
})().catch(error=>{console.error(error);process.exitCode=1;});
