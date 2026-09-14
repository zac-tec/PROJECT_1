function displayDate(value){return String(value).replace(/\b(\d{4})-(\d{2})-(\d{2})\b/g,'$3-$2-$1');}
(()=>{
 const skip='script,style,input,textarea,code,pre';
 function format(node){
  if(node.nodeType===Node.TEXT_NODE){if(!node.parentElement?.closest(skip)){const s=displayDate(node.nodeValue);if(s!==node.nodeValue)node.nodeValue=s;}return;}
  if(node.nodeType!==Node.ELEMENT_NODE||node.matches(skip))return;
  for(const child of node.childNodes)format(child);
 }
 document.addEventListener('DOMContentLoaded',()=>{
  format(document.body);
  new MutationObserver(records=>{for(const r of records){if(r.type==='characterData')format(r.target);else for(const n of r.addedNodes)format(n);}}).observe(document.body,{subtree:true,childList:true,characterData:true});
 });
})();
