'use strict';
// Only visible labels are translated. Values, names and submitted tokens stay intact.
window.ODILang=(()=>{
 let lang='ru';try{lang=localStorage.getItem('odi-panel-language')||(/^ru/i.test(navigator.language)?'ru':'en');}catch(_){}
 if(!['ru','en'].includes(lang))lang='ru';
 const maps={ru:new Map(),en:new Map()};
 for(const [ru,en,cn] of window.ODITranslations){maps.ru.set(en.trim(),ru);maps.en.set(ru.trim(),en);if(cn){maps.ru.set(cn.trim(),ru);maps.en.set(cn.trim(),en);}}
 function t(s){s=String(s);const raw=s.trim(),trim=raw.replace(/\s+/g,' '),map=maps[lang];if(map.has(trim))return s.replace(raw,map.get(trim));
 if(trim.endsWith(':')){const stem=trim.slice(0,-1);if(map.has(stem.trim()))return s.replace(raw,map.get(stem.trim())+':');}
 const patterns=lang==='en'?[[/^VERIFIED bank=([01])$/,'Write verified · bank $1'],[/^WRITING bank=([01])$/,'Write in progress · bank $1'],[/^FAILED bank=([01])$/,'Write not verified · bank $1'],[/^Запись проверена · банк ([01])$/,'Write verified · bank $1'],[/^Запись выполняется · банк ([01])$/,'Write in progress · bank $1'],[/^Запись не подтверждена · банк ([01])$/,'Write not verified · bank $1'],[/^Банк (\d)$/,'Bank $1'],[/^банк (\d)$/,'bank $1'],[/^ОБРАЗ (\d)$/,'IMAGE $1'],[/^Следующая загрузка: банк (\d)$/,'Next boot: bank $1'],[/^Следующая загрузка: не определена$/,'Next boot: unknown'],[/^Разделы: (.*)$/,'Partitions: $1'],[/^Текущее значение: (.*)$/,'Current value: $1'],[/^Текущее OMCI-значение: (.*)$/,'Current OMCI value: $1'],[/^Для следующей загрузки выбран банк (\d)\.$/,'Bank $1 selected for the next boot.'],[/^Загрузка из банка (\d)\?$/,'Boot from bank $1?'],[/^Добавление тега VLAN (\d+)$/,'Add VLAN tag $1'],[/^Файл: (.*)\. Штатный обработчик запишет прошивку\. Соединение может прерваться; питание отключать нельзя\.$/,'File: $1. The factory updater will write the firmware. The connection may close; do not disconnect power.']]:[[/^VERIFIED bank=([01])$/,'Запись проверена · банк $1'],[/^WRITING bank=([01])$/,'Запись выполняется · банк $1'],[/^FAILED bank=([01])$/,'Запись не подтверждена · банк $1'],[/^Write verified · bank ([01])$/,'Запись проверена · банк $1'],[/^Write in progress · bank ([01])$/,'Запись выполняется · банк $1'],[/^Write not verified · bank ([01])$/,'Запись не подтверждена · банк $1'],[/^Invalid value: (.*)$/,'Недопустимое значение: $1'],[/^Unsupported field: (.*)$/,'Неподдерживаемый параметр: $1'],[/^Read-back failed for (.*); rollback=(.*)\. Reload and verify settings\.$/,'Ошибка проверки записи $1; откат: $2. Перечитайте и проверьте настройки.']];
 for(const [re,replacement] of patterns)if(re.test(trim))return s.replace(raw,trim.replace(re,replacement));return s;
 }
 const originals=new WeakMap(),attrs=new WeakMap();
 function apply(root=document){const doc=root.ownerDocument||root,walker=doc.createTreeWalker(root,4);let n;
 while((n=walker.nextNode())){if(!n.parentElement||n.parentElement.closest('script,style,textarea,pre,code,[data-no-translate],.mono,dd'))continue;
  // An option without a value submits its text. Freeze its original token before translating.
  if(n.parentElement.tagName==='OPTION'&&!n.parentElement.hasAttribute('value'))n.parentElement.setAttribute('value',n.parentElement.textContent);
  const old=originals.get(n),source=old&&n.nodeValue===old.result?old.source:n.nodeValue,result=t(source);originals.set(n,{source,result});if(n.nodeValue!==result)n.nodeValue=result;
 }
 for(const el of root.querySelectorAll('[aria-label],[title]')){const saved=attrs.get(el)||{};for(const name of ['aria-label','title']){if(!el.hasAttribute(name))continue;const current=el.getAttribute(name),old=saved[name],source=old&&old.result===current?old.source:current,result=t(source);saved[name]={source,result};if(current!==result)el.setAttribute(name,result);}attrs.set(el,saved);}
 doc.documentElement.lang=lang;
 }
 function watch(doc=document){apply(doc);let scheduled=false;new MutationObserver(()=>{if(scheduled)return;scheduled=true;queueMicrotask(()=>{scheduled=false;apply(doc);});}).observe(doc.documentElement,{childList:true,subtree:true,characterData:true});}
 function set(next,persist=true){if(!['ru','en'].includes(next))return;lang=next;if(persist)try{localStorage.setItem('odi-panel-language',lang);}catch(_){}apply(document);const selector=document.getElementById('language');if(selector)selector.value=lang;document.querySelectorAll('iframe').forEach(f=>{try{if(f.contentWindow.ODILang)f.contentWindow.ODILang.set(next,false);else if(f.hasAttribute('srcdoc'))apply(f.contentDocument);}catch(_){}});window.dispatchEvent(new Event('odi-language-change'));}
 window.addEventListener('storage',e=>{if(e.key==='odi-panel-language')set(e.newValue,false);});
 return{t,apply,watch,set,get:()=>lang};
})();
