'use strict';
function mods(){return header('Моды Anime4000','Изменения применяются после отдельной перезагрузки. Выберите только нужные исправления.')+
 card('Исправление скорости','Сохраняется отдельно от остальных модов.',`<div class="grid">${field('MOD_SPEED','Исправление отдачи 2,5G',{options:{0:'Выключено',1:'Включено'},hint:'Снимает ограничения bandwidth на портах в режимах LAN_SPEED_MODE 4, 5 и 6. Режим порта не переключает.'})}</div>`,'mod-speed')+
 card('Подмена версий Anime4000','Сохраняется отдельно от остальных модов.',`<div class="grid">${field('MOD_SWVER','Подмена версий Anime4000',{options:{0:'Только явно заданные версии',1:'Версии Anime4000 с резервным значением'},hint:'В режиме OLT 3: пользовательская версия, а при пустом поле — метка sw_version соответствующего банка. Если отключено, применяются только явно заданные пользовательские версии.'})}</div>`,'mod-versions')+
 card('Исправление таблицы VLAN / ME 84','Выберите один алгоритм. Одновременный запуск двух исправлений запрещён.',`<div class="grid">${field('MOD_VLAN','Алгоритм VLAN',{options:{off:'Выключено',tag:'По VLAN ID или Entity ID',fwdop:'По парам Entity ID:FwdOp'}})}${field('MOD_FWDOP','FwdOp для фильтра',{max:4,pattern:'0x[0-9a-fA-F]{2}',hint:'Пример: 0x02. Значение применяется к выбранным записям.'})}${field('MOD_VLANS','VLAN ID через пробел',{max:120,pattern:'[1-9][0-9]{0,3}( [1-9][0-9]{0,3})*',hint:'Пример: 100 200. Диапазон 1–4094.'})}${field('MOD_ENTITIES','Entity ID через пробел',{max:120,pattern:'0x[0-9a-fA-F]{1,4}( 0x[0-9a-fA-F]{1,4})*',hint:'Пример: 0x0101 0x0102.'})}${field('MOD_PAIRS','Пары Entity ID:FwdOp',{max:120,pattern:'0x[0-9a-fA-F]{1,4}:0x[0-9a-fA-F]{2}(,0x[0-9a-fA-F]{1,4}:0x[0-9a-fA-F]{2})*',hint:'Пример: 0x0101:0x02,0x0102:0x02.'})}</div><div class="mode-info">Цикл выполняется каждые 30 секунд. Без фильтра исправление не включается. Ручной VLAN прошивки и исправления ME 84 — разные механизмы; сочетайте их только для известной проблемы.</div>`,'mod-vlan')+
 modRuntime();}
function modVlanControls(){
 const f=document.querySelector('[data-settings="mod-vlan"]');if(!f)return;
 const mode=f.elements.MOD_VLAN.value;
 for(const key of ['MOD_VLANS','MOD_ENTITIES','MOD_FWDOP'])f.elements[key].disabled=mode!=='tag'||value(key)===null;
 f.elements.MOD_PAIRS.disabled=mode!=='fwdop'||value('MOD_PAIRS')===null;
 f.elements.MOD_FWDOP.required=mode==='tag';f.elements.MOD_PAIRS.required=mode==='fwdop';
}
async function saveMods(f){
 if(preview||busy)return;const params={};
 for(const el of Array.from(f.elements)){
  if(!el.name||el.disabled||!['INPUT','SELECT'].includes(el.tagName))continue;
  if(!el.reportValidity())return;
  if(controlChanged(el))params[el.name]=el.value;
 }
 if(!Object.keys(params).length){toast('Нет изменений для сохранения.');return;}
 if(f.dataset.settings==='mod-vlan'&&f.elements.MOD_VLAN.value==='tag'&&!f.elements.MOD_VLANS.value&&!f.elements.MOD_ENTITIES.value){toast('Укажите VLAN ID или Entity ID.',true);return;}
 const message=f.dataset.settings==='mod-vlan'?'Изменения вступят в силу после перезагрузки. Исправления VLAN могут изменить прохождение трафика.':'Сохраняются только параметры этого блока. Для применения потребуется перезагрузка.';
 if(!await confirmAction('Сохранить этот мод?',message))return;
 const drafts=captureDrafts(f);busy=true;const buttons=f.querySelectorAll('button');buttons.forEach(b=>b.disabled=true);
 try{await api('mods',params);dirty=false;busy=false;await load();restoreDrafts(drafts);dirty=drafts.length>0;modVlanControls();formStatus();toast('Мод сохранён. Для применения перезагрузите ONU.');}
 catch(e){busy=false;buttons.forEach(b=>b.disabled=false);toast(e.message,true);}
}
function bindMods(){modVlanControls();}
