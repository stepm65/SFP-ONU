'use strict';
const nativeAlert=window.alert.bind(window),nativeConfirm=window.confirm.bind(window);
window.alert=message=>nativeAlert(ODILang.t(message));window.confirm=message=>nativeConfirm(ODILang.t(message));
function prepareNativeButtons(){document.querySelectorAll('input[type=submit],input[type=reset],input[type=button]').forEach(input=>{
 const button=document.createElement('button');for(const a of input.attributes)button.setAttribute(a.name,a.value);
 button.textContent=input.value;button.value=input.value;button.onclick=input.onclick;input.replaceWith(button);
});}
document.addEventListener('DOMContentLoaded',()=>{
 document.body.classList.toggle('embedded',parent!==window);prepareNativeButtons();ODILang.watch();
 if(parent!==window){try{ODILang.set(parent.ODILang.get(),false);frameElement?.dispatchEvent(new Event('odi-native-ready'));}catch(_){} }
 else {const label=document.createElement('label');label.className='language-control';label.textContent='Language / Язык ';const select=document.createElement('select');select.id='language';select.innerHTML='<option value="ru">Русский</option><option value="en">English</option>';select.value=ODILang.get();select.onchange=()=>ODILang.set(select.value);label.append(select);document.body.prepend(label);}
 document.addEventListener('input',()=>{window.nativeDirty=true;});document.addEventListener('change',()=>{window.nativeDirty=true;});
 document.addEventListener('submit',()=>{window.nativeDirty=false;});
 window.addEventListener('beforeunload',e=>{if(window.nativeDirty){e.preventDefault();e.returnValue='';}});
});
