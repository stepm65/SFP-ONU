'use strict';
const nativeAlert=window.alert.bind(window),nativeConfirm=window.confirm.bind(window);
window.alert=message=>nativeAlert(ODILang.t(message));window.confirm=message=>nativeConfirm(ODILang.t(message));
function prepareNativeButtons(){document.querySelectorAll('input[type=submit],input[type=reset],input[type=button]').forEach(input=>{
 const button=document.createElement('button');for(const a of input.attributes)button.setAttribute(a.name,a.value);
 button.textContent=input.value;button.value=input.value;button.onclick=input.onclick;input.replaceWith(button);
});}
function prepareNativeLayout(){
 // Change presentation only. Keep form nodes, names, handlers and posted values.
 document.querySelectorAll('table').forEach(table=>{
  if(table.classList.contains('native-table'))return;
  const rows=Array.from(table.rows).filter(row=>row.closest('table')===table);
  const columns=Math.max(0,...rows.map(row=>Array.from(row.cells).reduce((n,cell)=>n+cell.colSpan,0)));
  const controls=table.querySelector('input,select,textarea,button');
  table.classList.add('native-table');
  for(const element of [table,...table.querySelectorAll('tr,td,th')]){
   for(const name of ['width','height','bgcolor','border','cellpadding','cellspacing'])element.removeAttribute(name);
  }
  if(columns<=1&&!controls){
   table.classList.add('native-note');
   for(const row of rows)if(!row.textContent.trim()&&!row.querySelector('img,input,button,select,textarea'))row.hidden=true;
  }else if(columns<=2){
   table.classList.add('native-properties');
   for(const row of rows)if(row.cells.length===1&&row.cells[0].colSpan>1)row.classList.add('native-section');
  }else{
   table.classList.add('native-grid');
   const scroll=document.createElement('div');scroll.className='native-table-scroll';table.before(scroll);scroll.append(table);
  }
 });
}
document.addEventListener('DOMContentLoaded',()=>{
 document.body.classList.toggle('embedded',parent!==window);prepareNativeButtons();prepareNativeLayout();ODILang.watch();
 if(parent!==window){try{ODILang.set(parent.ODILang.get(),false);frameElement?.dispatchEvent(new Event('odi-native-ready'));}catch(_){} }
 else {const label=document.createElement('label');label.className='language-control';label.textContent='Language / Язык ';const select=document.createElement('select');select.id='language';select.innerHTML='<option value="ru">Русский</option><option value="en">English</option>';select.value=ODILang.get();select.onchange=()=>ODILang.set(select.value);label.append(select);document.body.prepend(label);}
 document.addEventListener('input',()=>{window.nativeDirty=true;});document.addEventListener('change',()=>{window.nativeDirty=true;});
 document.addEventListener('submit',()=>{window.nativeDirty=false;});
 if(parent!==window){try{
  for(const input of document.querySelectorAll('input[name="submit-url"]'))if(input.value)input.value=parent.nativeFrameURL(input.value);
 }catch(_){} }
 window.addEventListener('beforeunload',e=>{if(window.nativeDirty){e.preventDefault();e.returnValue='';}});
});
