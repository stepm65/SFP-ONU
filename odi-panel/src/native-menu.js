'use strict';
const nativePages=[
 ['status','Состояние устройства','/status.asp','Состояние'],['pon','Состояние PON','/status_pon.asp','Состояние'],
 ['lan','Настройки LAN / IP','/tcpiplan.asp','Сеть'],['wanmode','Режим WAN','/wanmode.asp','Сеть'],['wan','Подключение PON WAN','/boaform/formWanRedirect?redirect-url=/multi_wan_generic.asp&if=pon','Сеть'],
 ['gpon','Настройки GPON','/gpon.asp','Сеть'],['epon','Настройки EPON','/epon.asp','Сеть'],['olt-vlan','Штатный VLAN и таблица OLT','/vlan.asp','Сеть'],['omci','Информация OMCI','/omci_info.asp','Сеть'],
 ['arp','Таблица ARP','/arptable.asp','Диагностика'],['ping','Ping','/ping.asp','Диагностика'],
 ['backup','Обслуживание устройства','/saveconf.asp','Обслуживание'],['password','Пароль администратора','/password.asp','Обслуживание'],['timer','Перезагрузка по таймеру','/rebootTime.asp','Обслуживание'],['factory-reboot','Перезагрузка','/reboot.asp','Обслуживание'],['factory-upgrade','Обновление прошивки','/upgrade.asp','Обслуживание'],
 ['stats','Статистика интерфейсов','/stats.asp','Статистика'],['pon-stats','Статистика PON','/admin/pon-stats.asp','Статистика']
];
const nativeAliases={'native-wanmode':'wan','native-wan':'wan','native-epon':'identity','native-gpon':'identity','native-omci':'identity','native-olt-vlan':'vlan','native-factory-reboot':'firmware','native-factory-upgrade':'firmware','native-backup':'profiles'};
// An SDK template on disk is not proof that the OEM exposes or supports it.
// Only links returned by the stock menu enable the generic WAN forms.
const nativeWan={pon:null,mode:null};
const duplicatePaths=new Set(['/wanmode.asp','/multi_wan_generic.asp','/boaform/formWanRedirect','/epon.asp','/gpon.asp','/omci_info.asp','/vlan.asp','/linkmode.asp','/linkmode_eth.asp','/reboot.asp','/upgrade.asp','/saveconf.asp']);
function nativeNavigation(){
 const nav=document.getElementById('native-nav');
 nav.innerHTML=rootSections.map(([id,label,path])=>'<a href="#'+id+'" '+(id.startsWith('native-')?'data-native="'+id.slice(7)+'"':'data-tab="'+id+'"')+'><svg class="nav-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="'+path+'"/></svg><span>'+esc(label)+'</span></a>').join('');ODILang.apply(nav);if(typeof tab!=='undefined')paintSectionNav();
}
function nativePage(){if(location.hash==='#native-recovery')return header('Восстановление доступа','Запасной вход в управление устройством.')+card('Резервный интерфейс','Открывает сохранённый интерфейс прошивки в новой вкладке. Используйте, если основная панель недоступна.',(preview?'<button type="button" class="button secondary" disabled>Открыть резервный интерфейс</button><p class="muted">Доступно только на устройстве.</p>':'<a class="button secondary" href="/legacy.html" target="_blank" rel="noopener">Открыть резервный интерфейс</a>')+'<p class="muted">Прямой адрес: <code>/legacy.html</code></p>');const entry=nativePages.find(p=>p[0]===location.hash.slice(8));if(!entry)return header('Штатные разделы','');const [,label,url]=entry;
 return header(esc(label),'Формы используют штатные обработчики прошивки. Некоторые действия применяются немедленно.')+
 (['gpon','omci'].includes(entry[0])?'<div class="banner">Штатные версии OMCI могут переопределяться при загрузке. Пользовательские версии задаются в разделе ONU / OMCI.</div>':'')+
 (preview?(window.ODINativePreview?.[url]?`<iframe sandbox="allow-same-origin" class="native-frame" title="${esc(label)}" srcdoc="${esc(window.ODINativePreview[url])}"></iframe>`:'<div class="card empty"><p>Штатная страница доступна только на устройстве.</p></div>'):`<p class="native-external"><a href="${esc(url)}" target="_blank" rel="noopener">Открыть отдельно ↗</a></p><iframe class="native-frame" name="view" title="${esc(label)}" src="${esc(url)}"></iframe>`);
}
async function discoverNativeMenu(){if(preview)return;try{
 const res=await fetch('/code.asp',{credentials:'same-origin',cache:'no-store'});if(!res.ok)return;
 const doc=new DOMParser().parseFromString(await res.text(),'text/html'),links=Array.from(doc.querySelectorAll('a[target="view"][href]')),resolved=[],wan={pon:null,mode:null};
 for(const a of links){let u;try{u=new URL(a.getAttribute('href'),location.origin+'/');}catch(_){continue;}if(u.origin!==location.origin||!/^\/(?:[\w/-]+\.asp|boaform\/(?:admin\/)?formWanRedirect)$/.test(u.pathname))continue;
  const url=u.pathname+u.search,path=u.pathname.replace(/^\/admin\//,'/'),pon=(u.searchParams.get('if')||'').toLowerCase()==='pon';let found;
  if(path==='/wanmode.asp'){wan.mode=url;found=nativePages.find(p=>p[0]==='wanmode');}
  else if((/^\/boaform\/(?:admin\/)?formWanRedirect$/.test(path)&&pon)||(['/multi_wan_generic.asp','/waneth.asp'].includes(path)&&(pon||/\bPON\b/i.test(a.textContent)))){wan.pon=url;found=nativePages.find(p=>p[0]==='wan');}
  else found=nativePages.find(p=>p[2]===url||p[2]===url.replace(/^\/admin\//,'/'));
  if(found){if(!resolved.some(p=>p[0]===found[0]))resolved.push([found[0],found[1],url,found[3]]);}else if(!duplicatePaths.has(path))resolved.push(['extra-'+resolved.length,a.textContent.trim(),url,'Штатные разделы']);
 }
 Object.assign(nativeWan,wan);
 if(resolved.length){for(const page of resolved){const i=nativePages.findIndex(p=>p[0]===page[0]);if(i<0)nativePages.push(page);else nativePages[i]=page;}nativeNavigation();}
}catch(_){} }

function nativeEmbed(url,label){
 if(preview)return window.ODINativePreview?.[url]?`<iframe sandbox="allow-same-origin" class="native-frame" title="${esc(label)}" srcdoc="${esc(window.ODINativePreview[url])}"></iframe>`:'<p>Штатная страница доступна только на устройстве.</p>';
 return `<iframe class="native-frame" title="${esc(label)}" src="${esc(url)}"></iframe>`;
}
function wan(){if(!nativeWan.pon&&!nativeWan.mode)return vlan();return header('WAN','Штатные разделы WAN, доступные в меню этой прошивки.')+
 (nativeWan.pon?card('Подключение через PON','Форма присутствует в штатном меню устройства. Таблица WAN задаётся отдельно от ручного PVID; изменения могут влиять на передачу трафика.',nativeEmbed(nativeWan.pon,'Подключение через PON')):'')+
 (nativeWan.mode?card('Расширенные настройки','Выбор типа WAN-интерфейса общего SDK. Это не переключатель GPON/EPON.',`<details><summary>Выбор WAN-интерфейса</summary><p class="muted">Шаблон содержит ATM, Ethernet, PTM и Wireless. Их наличие не означает поддержку стиком; менять этот параметр для обычной настройки GPON не требуется.</p>${nativeEmbed(nativeWan.mode,'Выбор WAN-интерфейса')}</details>`):'');}

const nativeFrameBindings=new Map();
function sizeNativeFrames(){
 for(const [frame,binding] of nativeFrameBindings)if(!frame.isConnected){binding.dispose();nativeFrameBindings.delete(frame);}
 document.querySelectorAll('.native-frame').forEach(frame=>{
  if(nativeFrameBindings.has(frame)){nativeFrameBindings.get(frame).refresh();return;}
  let doc=null,content=null,observer=null,mutation=null,pending=null;
  const request=window.requestAnimationFrame?.bind(window)||((fn)=>setTimeout(fn,16)),cancel=window.cancelAnimationFrame?.bind(window)||clearTimeout;
  function stopDocument(){observer?.disconnect();mutation?.disconnect();observer=mutation=null;if(pending!==null)cancel(pending);pending=null;doc=content=null;}
  function dispose(){stopDocument();frame.removeEventListener('load',fit);frame.removeEventListener('odi-native-ready',fit);window.removeEventListener('resize',schedule);}
  function schedule(){if(pending===null)pending=request(measure);}
  function measure(){pending=null;
   if(!frame.isConnected){dispose();nativeFrameBindings.delete(frame);return;}
   try{
    if(!content||!content.isConnected||doc!==frame.contentDocument||!frame.getClientRects().length)return;
    // Quirks-mode body boxes can fill the iframe viewport. Measure an intrinsic
    // content block instead, so changing the frame height cannot change the input.
    const rect=content.getBoundingClientRect();if(rect.height<=0)return;
    const bodyStyle=doc.defaultView.getComputedStyle(doc.body),frameStyle=getComputedStyle(frame),pixels=(style,key)=>parseFloat(style[key])||0;
    const height=Math.max(260,Math.ceil(rect.height+['paddingTop','paddingBottom','marginTop','marginBottom','borderTopWidth','borderBottomWidth'].reduce((sum,key)=>sum+pixels(bodyStyle,key),0)+pixels(frameStyle,'borderTopWidth')+pixels(frameStyle,'borderBottomWidth')));
    if(!Number.isFinite(height))return;
    if(frame.style.minHeight!=='0px')frame.style.minHeight='0px';if(frame.style.height!==height+'px')frame.style.height=height+'px';
   }catch(_){}
  }
  function fit(){try{
   const next=frame.contentDocument;if(!next?.body||next.readyState==='loading'||!next.body.childNodes.length)return;
   if(next===doc&&content?.parentElement===doc.body){schedule();return;}
   stopDocument();doc=next;if(preview)ODILang.apply(doc);
   content=doc.createElement('div');content.className='odi-native-content';content.style.display='flow-root';
   // Move existing nodes: native form handlers, tokens, drafts and selected files survive.
   while(doc.body.firstChild)content.append(doc.body.firstChild);doc.body.append(content);
   if(typeof ResizeObserver!=='undefined'){observer=new ResizeObserver(schedule);observer.observe(content);}
   else if(typeof MutationObserver!=='undefined'){mutation=new MutationObserver(schedule);mutation.observe(content,{childList:true,subtree:true,attributes:true,characterData:true});}
   doc.fonts?.ready.then(schedule);schedule();
  }catch(_){} }
  nativeFrameBindings.set(frame,{dispose,refresh:fit});
  frame.addEventListener('load',fit);frame.addEventListener('odi-native-ready',fit);window.addEventListener('resize',schedule);fit();
 });
}
