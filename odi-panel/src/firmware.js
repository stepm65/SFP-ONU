'use strict';
function firmwareUpload(){
 const active=state.sw_active,ready=['0','1'].includes(active)&&state.sw_commit===active;
 return card('Установка в выбранный банк','Поддерживаются подготовленные TAR-образы на основе ODI SFU 240408.',`<form id="upload"><div class="grid"><div class="field"><label for="upload-bank">Банк для записи</label><select id="upload-bank" name="bank" ${!ready||preview?'disabled':''}>${['0','1'].map(n=>`<option value="${n}" ${n===active?'disabled':'selected'}>${ODILang.t('Банк '+n)}${n===active?' · '+ODILang.t('Текущий'):''}</option>`).join('')}</select><small>Работающий банк защищён от перезаписи.</small></div><div class="field"><label for="firmware-file">Файл прошивки TAR</label><input id="firmware-file" type="file" name="binary" accept=".tar" required ${!ready||preview?'disabled':''}></div></div><p class="muted">После записи проверяются данные в памяти. Выбор следующей загрузки и перезагрузка выполняются отдельно.</p>${!ready?'<div class="banner warn">Перед установкой выберите текущий банк для следующей загрузки и обновите данные.</div>':''}<div class="actions" style="margin-top:18px"><button class="button" type="submit" ${!ready||preview?'disabled':''}>Проверить и записать</button></div><p id="upload-status" role="status" aria-live="polite"></p></form>${state.firmware_status?`<p class="muted">${esc(ODILang.t('Последняя операция'))}: <span>${esc(state.firmware_status)}</span></p>`:''}`);
}
const firmwareErrors={AUTH:'Требуется вход администратора.',CSRF:'Обновите страницу и повторите загрузку.',METHOD:'Недопустимый запрос.',TYPE:'Недопустимый запрос.',LENGTH:'Выберите TAR-файл размером не более 8 МиБ.',ENVELOPE:'Недопустимый запрос.',BANK:'Не выбран банк для записи.',BUSY:'Другая операция уже выполняется.',BOOT_STATE:'Перед установкой выберите текущий банк для следующей загрузки и обновите данные.',ACTIVE_BANK:'Работающий банк защищён от перезаписи.',PARTITIONS:'Разметка устройства не соответствует этой сборке.',RECEIVE:'Не удалось принять файл прошивки.',TRUNCATED:'Файл загружен не полностью.',ARCHIVE:'Неверная структура TAR-архива.',KERNEL:'Неподдерживаемое ядро. Разрешена только проверенная основа ODI SFU 240408.',UPDATER:'Скрипт обновления отличается от проверенного штатного варианта.',HARDWARE:'Образ предназначен для другой аппаратной платформы.',ROOTFS:'Неверный формат или размер rootfs.',VERSION:'Не удалось проверить версию образа.',CHECKSUM:'Контрольная сумма образа не совпадает.',MARKER:'Не удалось сохранить состояние проверки банка.',WRITE:'Запись не завершена. Не загружайтесь из целевого банка.',READBACK:'Записанные данные не прошли проверку. Не загружайтесь из целевого банка.',BOOT_CHANGED:'Во время записи изменилось состояние загрузки. Проверьте банки перед перезагрузкой.'};
const firmwareUnknown='Не удалось получить результат. Обновите данные и проверьте состояние операции перед перезагрузкой.';
function sendFirmware(file,bank,onEvent,onTransfer){return new Promise((resolve,reject)=>{
 const request=new XMLHttpRequest(),rows={};let offset=0,pending='',invalid=false;
 request.open('POST','upload.cgi');request.setRequestHeader('Content-Type','application/octet-stream');
 // Incremental responseText works without ReadableStream and includes upload byte events.
 function consume(final=false){
  const text=request.responseText||'';if(text.length>65536){invalid=true;return;}
  pending+=text.slice(offset);offset=text.length;const lines=pending.split('\n');pending=lines.pop();if(final&&pending){lines.push(pending);pending='';}
  for(const line of lines){const at=line.indexOf('=');if(at<1)continue;const key=line.slice(0,at),value=line.slice(at+1).trim();rows[key]=value;
   if(key==='phase')onEvent(key,value);
   if(key==='log'&&/^(?:[0-9a-f]{2})*$/.test(value))onEvent(key,decode(value));
  }
 }
 request.onprogress=()=>consume();request.upload.onprogress=e=>{if(e.lengthComputable)onTransfer(e.loaded,e.total);};
 request.upload.onload=()=>onEvent('sent','');
 request.onload=()=>{
  consume(true);
  if((!rows.error&&(request.status===401||request.status===403))||(request.responseText||'').trimStart().startsWith('<')){reject(new Error(firmwareErrors.AUTH));return;}
  if(invalid||request.status<200||request.status>=300||rows.error||rows.ok!=='1'||rows.bank!==bank){reject(new Error(firmwareErrors[rows.error]||firmwareUnknown));return;}
  resolve(rows);
 };
 request.onerror=request.ontimeout=request.onabort=()=>reject(new Error('Связь со стиком прервана. Не отключайте питание. Обновите данные и проверьте состояние банка.'));
 // No client timeout or cancellation: flash writing may outlive the connection.
 request.send(new Blob(['csrf='+state.csrf+'\nbank='+bank+'\n',file]));
});}
function bindFirmware(){const form=document.getElementById('upload');if(!form)return;form.onsubmit=async e=>{
 e.preventDefault();if(preview||busy)return;
 const file=form.elements.binary.files[0],bank=form.elements.bank.value;
 if(!file||!file.name.toLowerCase().endsWith('.tar')||file.size>8388500){toast('Выберите TAR-файл размером не более 8 МиБ.',true);return;}
 if(bank===state.sw_active||state.sw_commit!==state.sw_active){toast(firmwareErrors.BOOT_STATE,true);return;}
 if(!await confirmAction('Записать прошивку в выбранный банк?',ODILang.t('Банк '+bank)+' — '+file.name+'\n'+ODILang.t('Содержимое целевого банка будет заменено. Не отключайте питание до завершения проверки.')))return;
 busy=true;dirty=true;document.getElementById('refresh').disabled=true;Array.from(form.elements).forEach(el=>el.disabled=true);
 await pauseLive();
 const status=document.getElementById('upload-status');status.textContent=ODILang.t('Загрузка, запись и проверка. Не отключайте питание.');
 document.getElementById('upload-progress')?.remove();
 const progress=document.createElement('div');progress.id='upload-progress';progress.innerHTML='<div class="upload-heading"><strong id="upload-phase" role="status" aria-live="polite"></strong><span id="upload-elapsed" class="muted"></span></div><p id="upload-detail"></p><progress aria-label="'+bi('Выполнение обновления','Update progress')+'"></progress><ol class="progress-phases"></ol><p class="muted">'+bi('Запись и проверка памяти не подтверждают загрузку нового банка. Факт загрузки отображается отдельно после перезапуска.','Writing and memory verification do not confirm that the new bank has booted. Boot status is shown separately after restart.')+'</p><details><summary>'+bi('Журнал обновления','Update log')+'</summary><pre id="upload-log"></pre></details>';status.after(progress);
 const phases=['receiving','checking','writing','readback','verified'],labels=[bi('Передача файла','File transfer'),bi('Проверка архива','Archive check'),bi('Запись памяти','Flash write'),bi('Проверка чтением','Read-back check'),bi('Запись подтверждена','Write verified')];
 const hints=[bi('Передаём файл на стик.','Sending the file to the stick.'),bi('Проверяем структуру TAR, совместимость и контрольные суммы.','Checking TAR structure, compatibility and checksums.'),bi('Стираем и записываем выбранный банк. Дождитесь проверки чтением.','Erasing and writing the selected bank. Wait for read-back verification.'),bi('Сравниваем содержимое памяти с файлом прошивки.','Comparing flash contents with the firmware file.'),bi('Данные совпадают. Выбор загрузки и перезагрузка выполняются отдельно.','Data matches. Boot selection and restart are separate actions.')];
 let current=0;const bar=progress.querySelector('progress'),heading=progress.querySelector('#upload-phase'),detail=progress.querySelector('#upload-detail'),started=Date.now();
 function showPhase(phase){const index=phases.indexOf(phase);if(index<current||index<0)return;current=index;
  heading.innerHTML='<span>'+bi('Этап','Stage')+'</span> '+(index+1)+' / 5 · <span>'+esc(ODILang.t(labels[index]))+'</span>';detail.textContent=ODILang.t(hints[index]);progress.dataset.phase=phase;
  progress.querySelector('.progress-phases').innerHTML=labels.map((label,i)=>'<li class="'+(i<index||index===4?'done':i===index?'current':'')+'" '+(i===index?'aria-current="step"':'')+'><b>'+((i<index||index===4)?'✓':i+1)+'</b><span>'+esc(label)+'</span></li>').join('');
  if(index===4){bar.max=100;bar.value=100;}else if(index>0)bar.removeAttribute('value');
 }
 function updateElapsed(){const seconds=Math.floor((Date.now()-started)/1000);progress.querySelector('#upload-elapsed').innerHTML='<span>'+bi('Прошло','Elapsed')+'</span> '+Math.floor(seconds/60)+':'+String(seconds%60).padStart(2,'0');}
 showPhase('receiving');updateElapsed();const elapsedTimer=setInterval(updateElapsed,1000);
 function event(key,value){if(key==='phase')showPhase(value);else if(key==='log')progress.querySelector('#upload-log').textContent=value||'—';else if(key==='sent'&&current===0)detail.textContent=bi('Файл передан. Ожидаем проверку архива на стике.','File sent. Waiting for the archive check on the stick.');}
 try{
  await sendFirmware(file,bank,event,(loaded,total)=>{if(current!==0||total<=0)return;const percent=Math.min(100,Math.floor(loaded/total*100));bar.max=100;bar.value=percent;detail.innerHTML='<span>'+bi('Передано','Transferred')+'</span> '+percent+'% · '+(loaded/1048576).toFixed(2)+' / '+(total/1048576).toFixed(2)+' <span>'+bi('МиБ','MiB')+'</span>';});
  showPhase('verified');clearInterval(elapsedTimer);updateElapsed();busy=false;dirty=false;await load();const nextStatus=document.getElementById('upload-status');
  if(nextStatus){nextStatus.textContent=bi('Прошивка записана и проверена. Теперь можно отдельно выбрать банк для загрузки.','Firmware written and verified. You can now select the bank for the next boot.');nextStatus.after(progress);}
  else document.getElementById('main').prepend(progress);
  toast('Прошивка записана и проверена. Теперь можно отдельно выбрать банк для загрузки.');
 }catch(err){busy=false;progress.dataset.failed='1';status.textContent=ODILang.t(err.message);heading.innerHTML='<span>'+bi('Обновление не подтверждено','Update not confirmed')+'</span> · <span>'+esc(ODILang.t(labels[current]))+'</span>';detail.textContent=ODILang.t(err.message);bar.removeAttribute('value');toast(err.message,true);Array.from(form.elements).forEach(el=>el.disabled=false);for(const option of form.elements.bank.options)option.disabled=option.value===state.sw_active;
 }finally{clearInterval(elapsedTimer);updateElapsed();document.getElementById('refresh').disabled=false;restartLive();}
};}
