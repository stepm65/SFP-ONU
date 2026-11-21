'use strict';
// Operator shell on the stick (api.cgi -> odi-terminal.sh). Off by default;
// enabling opens a 15-minute window. Limits are enforced on the device.
let termLog=[],termHistory=[],termHistoryAt=0,termRunning=false,termDeadline=0,termTicker=null,termDraft='';
const termQuick=['diag gpon get password','flash get GPON_PLOAM_PASSWD','flash get GPON_SN','omcicli mib get 7','cat /proc/uptime','ifconfig'];
const termDemo=[
 {cmd:'diag gpon get password',cwd:'/',out:'gpon get password \npassword: 0000000000 ',rc:'0',state:'done'},
 {cmd:'flash get GPON_PLOAM_FORMAT',cwd:'/',out:'GPON_PLOAM_FORMAT=0',rc:'0',state:'done'},
 {cmd:'flash get NO_SUCH_KEY',cwd:'/',out:'[ERR] Warning, unknown dir name: NO_SUCH_KEY\nGET fail.',rc:'1',state:'done'},
 {cmd:'cat /proc/uptime',cwd:'/',out:'84211.37 80912.55',rc:'0',state:'done'}
];
function termSync(data){
 for(const k of ['terminal_remaining','terminal_ttl','terminal_timeout','terminal_lan','terminal_cwd'])if(data[k]!==undefined)state[k]=data[k];
 termDeadline=Date.now()+(parseInt(state.terminal_remaining||'0',10)||0)*1000;
}
function termLeft(){if(!termDeadline)termSync({});return Math.max(0,Math.round((termDeadline-Date.now())/1000));}
function termClock(s){return Math.floor(s/60)+':'+String(s%60).padStart(2,'0');}
function termPrompt(cwd){return 'root@ODI:'+(cwd||'/')+'#';}
function termEntry(e){
 const note=e.pending?bi('выполняется…','running…'):e.error?e.error:e.state==='timeout'?bi('Остановлено: превышено время ','Stopped: time limit of ')+esc(state.terminal_timeout||'20')+bi(' с',' s'):e.state==='aborted'?bi('Прервано','Aborted'):'';
 const meta=[note?'<span class="term-note'+(e.error||e.state!=='done'?' bad':'')+'">'+esc(note)+'</span>':'',!e.pending&&!e.error&&e.rc!=='0'?'<span class="term-note bad">'+bi('код выхода ','exit code ')+esc(e.rc)+'</span>':'',e.truncated==='1'?'<span class="term-note bad">'+bi('вывод обрезан до 64 КБ','output cut at 64 KB')+'</span>':''].filter(Boolean).join('');
 return '<div class="term-entry"><div class="term-cmd"><span class="term-ps">'+esc(termPrompt(e.cwd))+'</span> '+esc(e.cmd)+'</div>'+(e.out?'<pre class="term-out">'+esc(e.out)+'</pre>':'')+(meta?'<div class="term-meta">'+meta+'</div>':'')+'</div>';
}
function terminal(){
 if(preview&&!termLog.length)termLog=termDemo.map(e=>({...e}));
 const left=termLeft(),on=left>0,lan=state.terminal_lan!=='0',ready=on&&lan&&!preview;
 const status=on?'<span class="badge green" id="term-status">'+bi('Включён · ','On · ')+termClock(left)+'</span>':'<span class="badge" id="term-status">'+bi('Выключен','Off')+'</span>';
 const screen=termLog.length?termLog.map(termEntry).join(''):'<p class="term-empty">'+(on?bi('Введите команду ниже. Вывод появится здесь.','Type a command below. Output appears here.'):bi('Терминал выключен. Включите его, чтобы выполнять команды.','The terminal is off. Turn it on to run commands.'))+'</p>';
 return header(bi('Терминал','Terminal'),bi('Команды выполняются на стике от имени root. Терминал открывается на 15 минут и закрывается сам.','Commands run on the stick as root. The terminal opens for 15 minutes and closes by itself.'))+
 '<section class="card terminal-card"><div class="card-head"><div><h2>'+bi('Командная строка','Command line')+'</h2><p>'+bi('Только из локальной сети. Одна команда за раз.','Local network only. One command at a time.')+'</p></div>'+status+'</div><div class="card-body">'+
 (lan?'':'<div class="banner warn">'+bi('Терминал доступен только с адреса из локальной сети. Откройте панель с компьютера в сети роутера.','The terminal accepts only local network addresses. Open the panel from a computer on the router network.')+'</div>')+
 '<div class="banner warn term-warn">'+bi('Ошибка в команде может оборвать связь с провайдером или испортить настройки стика. Не вводите команды, смысл которых вам неясен.','A wrong command can drop the provider link or break the stick settings. Do not run commands you do not understand.')+'</div>'+
 '<div class="actions term-switch">'+(on?'<button type="button" class="button secondary" data-term="enable" '+(preview||!lan?'disabled':'')+'>'+bi('Продлить до 15 минут','Extend to 15 minutes')+'</button><button type="button" class="button secondary" data-term="disable" '+(preview?'disabled':'')+'>'+bi('Выключить','Turn off')+'</button>':'<button type="button" class="button" data-term="enable" '+(preview||!lan?'disabled':'')+'>'+bi('Включить на 15 минут','Turn on for 15 minutes')+'</button>')+'</div>'+
 '<div class="term-screen" id="term-screen" role="log" aria-live="polite" aria-label="'+bi('Вывод терминала','Terminal output')+'">'+screen+'</div>'+
 '<form class="term-line" id="term-form" autocomplete="off"><label class="term-ps" for="term-input">'+esc(termPrompt(state.terminal_cwd))+'</label><input id="term-input" name="term-input" class="term-input" spellcheck="false" autocapitalize="off" maxlength="1024" placeholder="'+(preview?bi('в предпросмотре команды не выполняются','commands do not run in preview'):ready?bi('команда','command'):bi('терминал выключен','terminal is off'))+'" '+(ready&&!termRunning?'':'disabled')+'><button type="submit" class="button" '+(ready&&!termRunning?'':'disabled')+'>'+bi('Выполнить','Run')+'</button><button type="button" class="button secondary" data-term="kill" '+(termRunning?'':'disabled')+'>'+bi('Прервать','Abort')+'</button></form>'+
 '<div class="term-quick"><span class="muted">'+bi('Вставить:','Insert:')+'</span>'+termQuick.map(c=>'<button type="button" class="term-chip" data-term-insert="'+esc(c)+'" '+(ready?'':'disabled')+'>'+esc(c)+'</button>').join('')+'</div>'+
 '<div class="term-foot"><p class="muted">'+bi('Команда работает до ','A command runs up to ')+esc(state.terminal_timeout||'20')+bi(' с, вывод — до 64 КБ. Интерактивные программы (vi, top, less) не работают. Каждая команда выполняется в новом shell, сохраняется только текущий каталог. Стрелки ↑ и ↓ листают историю.',' s, output up to 64 KB. Interactive programs (vi, top, less) do not work. Each command runs in a new shell; only the current directory is kept. Use ↑ and ↓ for history.')+'</p><button type="button" class="button quiet" data-term="clear" '+(termLog.length?'':'disabled')+'>'+bi('Очистить экран','Clear screen')+'</button></div>'+
 '</div></section>';
}
function termPaint(){if(tab!=='terminal')return;const input=document.getElementById('term-input');if(input)termDraft=input.value;render();const next=document.getElementById('term-input');if(next){next.value=termDraft;if(!next.disabled)next.focus();}const screen=document.getElementById('term-screen');if(screen)screen.scrollTop=screen.scrollHeight;}
async function termAction(action){
 try{const data=await api('terminal_'+action);termSync(data);if(action==='enable')toast(bi('Терминал включён на 15 минут.','Terminal on for 15 minutes.'));if(action==='disable')toast(bi('Терминал выключен.','Terminal off.'));}
 catch(e){toast(e.message,true);}
 if(action!=='kill')termPaint();
}
async function termRun(cmd){
 if(termRunning||!cmd)return;
 const entry={cmd,cwd:state.terminal_cwd||'/',pending:true};termLog.push(entry);if(termLog.length>200)termLog.shift();
 if(termHistory[termHistory.length-1]!==cmd)termHistory.push(cmd);if(termHistory.length>100)termHistory.shift();termHistoryAt=termHistory.length;
 termRunning=true;termDraft='';termPaint();
 try{const data=await api('terminal_run',{command:cmd});termSync(data);Object.assign(entry,{pending:false,out:data.terminal_output||'',rc:data.terminal_rc,state:data.terminal_state,truncated:data.terminal_truncated});}
 catch(e){Object.assign(entry,{pending:false,error:e.message});}
 termRunning=false;termPaint();
}
function bindTerminal(){
 clearInterval(termTicker);termTicker=null;
 const form=document.getElementById('term-form');if(!form)return;
 const input=document.getElementById('term-input'),screen=document.getElementById('term-screen');
 if(screen)screen.scrollTop=screen.scrollHeight;
 form.onsubmit=e=>{e.preventDefault();termRun(input.value.trim());};
 input.onkeydown=e=>{
  if(e.key==='ArrowUp'&&termHistory.length){e.preventDefault();termHistoryAt=Math.max(0,termHistoryAt-1);input.value=termHistory[termHistoryAt];}
  if(e.key==='ArrowDown'&&termHistory.length){e.preventDefault();termHistoryAt=Math.min(termHistory.length,termHistoryAt+1);input.value=termHistory[termHistoryAt]||'';}
 };
 document.querySelectorAll('[data-term]').forEach(b=>b.onclick=()=>{const a=b.dataset.term;if(a==='clear'){termLog=[];termPaint();return;}termAction(a);});
 document.querySelectorAll('[data-term-insert]').forEach(b=>b.onclick=()=>{input.value=b.dataset.termInsert;input.focus();});
 if(termLeft()>0)termTicker=setInterval(()=>{const badge=document.getElementById('term-status');if(!badge||tab!=='terminal'){clearInterval(termTicker);termTicker=null;return;}const left=termLeft();if(left>0){badge.textContent=bi('Включён · ','On · ')+termClock(left);}else{clearInterval(termTicker);termTicker=null;termPaint();}},1000);
}
addEventListener('odi-language-change',()=>{if(typeof tab!=='undefined'&&tab==='terminal')termPaint();});
