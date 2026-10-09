'use strict';
function ploamHex(text,format){
 if(format==='1'){if(!/^[\x20-\x7e]{10}$/.test(text))throw new Error('ASCII PLOAM должен содержать ровно 10 печатных символов.');return encode(text);}
 if(!/^[0-9a-f]{20}$/i.test(text))throw new Error('HEX PLOAM должен содержать ровно 20 hex-цифр.');return text.toLowerCase();
}
function ploamAscii(hex){const plain=decode(hex);if(!/^[\x20-\x7e]{10}$/.test(plain))throw new Error('Этот пароль нельзя показать как печатный ASCII. Используйте HEX.');return plain;}
function controlValue(el){if(el.name==='GPON_PLOAM_PASSWD')return ploamHex(el.value,el.dataset.format||'0');return el.value;}
function setControlValue(el,val){el.value=el.name==='GPON_PLOAM_PASSWD'&&el.dataset.format==='1'?ploamAscii(val):val;}
function configurePloam(input,select,mode){input.dataset.format=mode;select.value=mode;input.maxLength=mode==='1'?10:20;input.pattern=mode==='1'?'[ -~]{10}':'[0-9a-fA-F]{20}';input.required=select.dataset.edited==='1';}
function bindPloamSwitch(input,select){select.onchange=()=>{
 const next=select.value,previous=input.dataset.format||'0';let converted=input.value,needsEntry=false;
 if(input.value){
  try{const hex=ploamHex(input.value,previous);converted=next==='1'?ploamAscii(hex):hex;}
  catch(_){
   // A format is also an input mode: allow choosing it before entering a
   // complete password. Retain the draft instead of discarding or padding it.
   try{ploamHex(input.value,next);}catch(_){needsEntry=true;}
  }
 }
 input.value=converted;select.dataset.edited='1';dirty=true;configurePloam(input,select,next);
 if(needsEntry)toast(next==='1'?'Формат переключён. Введите 10 печатных ASCII-символов или вернитесь в HEX, чтобы сохранить исходное значение.':'Формат переключён. Введите 20 hex-цифр пароля.');
};}
function bindPloam(){const input=document.querySelector('[name=GPON_PLOAM_PASSWD]'),select=document.getElementById('ploam-format');if(!input||!select)return;
 let mode=state.GPON_PLOAM_FORMAT==='1'?'1':'0';const hex=input.value;
 if(mode==='1'){try{input.value=ploamAscii(hex);}catch(_){mode='0';}}
 delete select.dataset.edited;configurePloam(input,select,mode);bindPloamSwitch(input,select);
}

function controlChanged(el){if(el.name==='GPON_PLOAM_PASSWD'&&el.value===''&&state[el.name]==='')return false;try{return controlValue(el)!==(el.name==='GPON_PLOAM_PASSWD'?String(state[el.name]||'').toLowerCase():state[el.name]);}catch(_){return true;}}
function captureDrafts(savedForm){return Array.from(document.querySelectorAll('[data-settings]')).filter(f=>f!==savedForm&&Array.from(f.querySelectorAll('input,select')).some(e=>(e.name&&(!e.disabled||f.dataset.settings.startsWith('mod-'))&&controlChanged(e))||e.dataset.edited==='1')).map(f=>({id:f.dataset.settings,fields:Array.from(f.querySelectorAll('input,select')).filter(e=>(!e.disabled||f.dataset.settings.startsWith('mod-'))&&(e.name||e.id==='ploam-format')).map(e=>({name:e.name,id:e.id,value:e.value,format:e.dataset.format,edited:e.dataset.edited}))}));}
function restoreDrafts(drafts){for(const draft of drafts){const f=document.querySelector('[data-settings="'+draft.id+'"]');if(!f)continue;for(const v of draft.fields){const el=v.name?f.elements[v.name]:document.getElementById(v.id);if(!el)continue;el.value=v.value;if(v.format!==undefined)el.dataset.format=v.format;if(v.edited!==undefined)el.dataset.edited=v.edited;}const input=f.elements.GPON_PLOAM_PASSWD,select=f.querySelector('#ploam-format');if(input&&select){configurePloam(input,select,input.dataset.format||'0');bindPloamSwitch(input,select);}}}
