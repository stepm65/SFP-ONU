'use strict';
async function endDeviceSession(){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
 try{
  // Preserve the stock logout endpoint and submitted field names.
  const response=await fetch('/boaform/admin/formLogout',{method:'POST',credentials:'same-origin',cache:'no-store',signal:controller.signal,headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({save:'Logout','submit-url':'/'})});
  await response.text();
  if(response.status===401||response.status===403)return;
  if(!response.ok)throw new Error('logout');
  // HTTP 200 can also be a factory error page. Probe the native root entry:
  // expired sessions can reset connections to deep paths on this Boa build.
  const probe=await fetch('/',{credentials:'same-origin',cache:'no-store',signal:controller.signal});
  const body=await probe.text();
  if(probe.status===401||probe.status===403)return;
  if(probe.ok&&new DOMParser().parseFromString(body,'text/html').querySelector('form[name="cmlogin"]'))return;
  throw new Error('session still active or unknown response');
 }finally{clearTimeout(timer);}
}
async function logoutPanel(event){
 event.preventDefault();if(busy)return;
 if(preview){toast(bi('Выход доступен только на устройстве.','Sign out is available on the device only.'));return;}
 const frame=document.querySelector('.native-frame');let frameDirty=false;try{frameDirty=!!frame?.contentWindow.nativeDirty;}catch(_){}
 if((dirty||frameDirty)&&!await confirmAction('Покинуть без сохранения','Несохранённые изменения на этой странице будут потеряны.'))return;
 busy=true;const button=document.getElementById('logout');button.setAttribute('aria-disabled','true');
 try{
  await pauseLive();await endDeviceSession();dirty=false;try{if(frame)frame.contentWindow.nativeDirty=false;}catch(_){}
  try{sessionStorage.removeItem('odi-panel-return');}catch(_){}
  location.replace('/');
 }catch(_){
  toast(bi('Не удалось подтвердить выход. Откройте страницу входа и проверьте соединение.','Sign-out could not be confirmed. Open the sign-in page and check the connection.'),true);
  let notice=document.getElementById('logout-error');if(!notice){notice=document.createElement('div');notice.id='logout-error';notice.className='banner warn';notice.innerHTML='<span>'+bi('Результат выхода не подтверждён.','Sign-out has not been confirmed.')+'</span><a class="button secondary" href="/">'+bi('Открыть страницу входа','Open sign-in page')+'</a>';document.getElementById('main').prepend(notice);}
  busy=false;button.removeAttribute('aria-disabled');restartLive();
 }
}
let renderedHash='',navigationPending=false;
function showAuth(){const el=document.getElementById('connection');el.textContent=bi('Сессия истекла','Session expired');el.className='status';let bar=document.getElementById('auth-expired');if(!bar){bar=document.createElement('div');bar.id='auth-expired';bar.className='banner warn';bar.innerHTML='<span>'+bi('Требуется авторизация. Несохранённые поля остаются открытыми.','Sign-in required. Unsaved fields remain open.')+'</span><a class="button secondary" href="/" target="_blank" rel="noopener" id="sign-in">'+bi('Войти снова','Sign in again')+'</a><button class="button secondary" id="retry-auth">'+bi('Проверить вход','Check sign-in')+'</button>';document.getElementById('main').prepend(bar);bar.querySelector('#sign-in').onclick=()=>{try{sessionStorage.setItem('odi-panel-return',renderedHash||'#overview');}catch(_){} };bar.querySelector('#retry-auth').onclick=async()=>{try{await api();bar.remove();el.textContent=bi('Вход подтверждён','Sign-in confirmed');el.className='status ready';}catch(e){toast(e.message,true);}};}}
function formStatus(){const pending=new Set((state.pending_keys||'').split('\n').filter(Boolean));for(const form of document.querySelectorAll('[data-settings]')){const changed=Array.from(form.elements).some(el=>(el.name&&!el.disabled&&controlChanged(el))||el.dataset.edited==='1');form.classList.toggle('has-draft',changed);const info=form.querySelector('.card-foot small');if(info)info.textContent=changed?bi('Есть несохранённые изменения.','Unsaved changes.'):Array.from(form.elements).some(el=>((el.name&&pending.has(el.name))||(el.name.startsWith('MOD_')&&pending.has('MODS'))))?bi('Сохранено и проверено; ожидает перезагрузки.','Saved and verified; reboot pending.'):bi('Показаны сохранённые настройки. Фактические значения смотрите в диагностике.','Saved settings shown. Check diagnostics for actual values.');for(const el of form.querySelectorAll('[name]')){let badge=el.closest('.field')?.querySelector('.field-status');if(!badge&&el.closest('.field')){badge=document.createElement('small');badge.className='field-status';el.closest('.field').append(badge);}if(badge){badge.hidden=!el.disabled&&!controlChanged(el)&&!pending.has(el.name);badge.textContent=el.disabled?bi('Недоступен или не используется в этом режиме','Unavailable or unused in this mode'):controlChanged(el)?bi('Не сохранено','Unsaved'):pending.has(el.name)?bi('Сохранено · ожидает перезагрузки','Saved · reboot pending'):bi('Сохранённое значение','Saved value');}}}
}
function bindUX(){bindLanguageSwitch();paintSectionNav();renderedHash=location.hash||'#overview';formStatus();bindDiagnostics();bindLogging();bindFullDebug();bindProfiles();restartLive();const restore=document.getElementById('restore-versions');if(restore)restore.onclick=restoreVersions;document.body.classList.remove('menu-open');document.getElementById('menu-toggle').setAttribute('aria-expanded','false');}
async function navigateChanged(){if(navigationPending)return;const next=location.hash||'#overview';if(next===renderedHash)return;if(busy){history.replaceState(null,'',renderedHash||'#overview');return;}const frame=document.querySelector('.native-frame');try{if(frame?.contentWindow.nativeDirty)dirty=true;}catch(_){}
 if(dirty){history.replaceState(null,'',renderedHash||'#overview');navigationPending=true;const proceed=await confirmAction('Перейти без сохранения?','Несохранённые изменения на этой странице будут потеряны.');navigationPending=false;if(!proceed)return;dirty=false;try{if(frame?.contentWindow)frame.contentWindow.nativeDirty=false;}catch(_){}history.replaceState(null,'',next);}if(Object.keys(state).length||next.startsWith('#native-'))render();
}
function initUX(){initLayout();document.getElementById('menu-toggle').onclick=()=>{document.body.classList.toggle('menu-open');document.getElementById('menu-toggle').setAttribute('aria-expanded',String(document.body.classList.contains('menu-open')));};document.getElementById('logout').onclick=logoutPanel;
 document.getElementById('main').addEventListener('input',formStatus);document.getElementById('main').addEventListener('change',formStatus);try{const saved=sessionStorage.getItem('odi-panel-return');if(saved&&/^#[a-z0-9-]+$/.test(saved)){history.replaceState(null,'',saved);sessionStorage.removeItem('odi-panel-return');}}catch(_){} }
