<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8"><meta name="odi-panel-version" content="1.9.7"><meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate"><meta http-equiv="Pragma" content="no-cache"><meta http-equiv="Expires" content="0">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ODI · Вход</title>
<script src="md5.js" type="text/javascript"></script>
<script>
function setpass() {
 <% passwd2xmit(); %>
}
</script>
<style>
:root{color-scheme:light;font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;color:#152235;background:#f4f6fa}*{box-sizing:border-box}body{margin:0;min-height:100vh;display:flex;flex-direction:column}header{display:flex;justify-content:space-between;align-items:center;padding:24px 32px;gap:20px}.brand{display:flex;align-items:center;gap:12px;font-size:23px;font-weight:750;letter-spacing:1px}.mark{display:grid;place-items:center;width:39px;height:39px;border:2px solid #2263df;border-radius:12px;color:#2263df}.brand small{display:block;font-size:9px;letter-spacing:1.8px;font-weight:500;color:#65748a}select,button,input{font:inherit}select{background:white;border:1px solid #d5dfea;border-radius:8px;padding:8px;color:#152235}main{flex:1;display:grid;place-items:center;padding:28px 20px 64px}.card{background:white;border:1px solid #e1e7ef;border-radius:18px;box-shadow:0 14px 44px #15223508;width:100%;max-width:420px;padding:36px}.eyebrow{font-size:11px;letter-spacing:1.5px;color:#65748a;margin:0 0 12px}h1{font-size:28px;line-height:1.2;margin:0 0 12px;letter-spacing:-.5px}.intro{color:#65748a;margin:0 0 28px;font-size:14px}label{display:block;font-size:13px;font-weight:600;margin:0 0 8px}.field{margin-bottom:20px}input:not([type=hidden]):not([type=submit]){width:100%;height:46px;border:1px solid #cbd5e1;border-radius:8px;padding:10px 12px;background:#fff;color:#152235}.password{position:relative}.password input{padding-right:86px!important}.reveal{position:absolute;right:5px;top:5px;height:36px;padding:0 10px;border:0;background:transparent;color:#2263df;font-size:12px;cursor:pointer}.submit{display:block;width:100%;height:46px;border:0;border-radius:8px;background:#2263df;color:white;font-weight:600;cursor:pointer;margin-top:26px}.submit:hover{background:#1954c7}:focus-visible{outline:3px solid #88b1ff;outline-offset:3px}.note{border-top:1px solid #e1e7ef;padding-top:20px;margin:24px 0 0;font-size:12px;color:#65748a}footer{text-align:center;padding:16px 20px 24px;color:#65748a;font-size:11px}.captcha{display:flex;gap:12px;align-items:center}.captcha img{border:1px solid #e1e7ef;border-radius:4px}@media(max-width:480px){header{padding:20px}.card{padding:28px 24px}main{padding:20px 16px 36px}h1{font-size:25px}}
</style>
</head>
<body>
<header><div class="brand"><span class="mark" aria-hidden="true">O</span><div>ODI<small>ONU MANAGEMENT</small></div></div><select id="language" aria-label="Язык / Language"><option value="ru">Русский</option><option value="en">English</option></select></header>
<main><section class="card" aria-labelledby="heading">
<p class="eyebrow">ODI PANEL</p>
<h1 id="heading" data-en="Sign in">Вход в управление</h1>
<p class="intro" data-en="Use your device account to continue.">Войдите под учётной записью устройства.</p>
<form action="/boaform/admin/formLogin" method="POST" name="cmlogin" onsubmit="setpass()">
<input type="hidden" name="challenge">
<div class="field"><label for="username" data-en="Username">Имя пользователя</label><input id="username" name="username" maxlength="30" autocomplete="username" autocapitalize="none" spellcheck="false"></div>
<div class="field"><label for="password" data-en="Password">Пароль</label><div class="password"><input id="password" type="password" name="password" maxlength="30" autocomplete="current-password"><button class="reveal" type="button" id="reveal" aria-controls="password" aria-pressed="false">Показать</button></div></div>
<!-- CAPTCHA -->
<input class="submit" type="submit" name="save" value="Войти" id="submit">
<input type="hidden" value="/admin/login.asp" name="submit-url">
</form>
<p class="note" data-en="Administrator access is required to manage settings.">Для управления настройками нужны права администратора.</p>
</section></main>
<footer><span data-en="Local device management">Локальное управление устройством</span> · ODI Panel 1.9.7</footer>
<script>
(function(){
 var language=document.getElementById('language'),pass=document.getElementById('password'),reveal=document.getElementById('reveal'),lang='ru';
 var labels=document.querySelectorAll('[data-en]');
 for(var i=0;i<labels.length;i++)labels[i].setAttribute('data-ru',labels[i].textContent);
 try{lang=localStorage.getItem('odi-panel-language')||(/^ru/i.test(navigator.language)?'ru':'en');}catch(e){}
 function paint(){
  lang=lang==='en'?'en':'ru';language.value=lang;document.documentElement.lang=lang;
  document.title=lang==='en'?'ODI · Sign in':'ODI · Вход';
  for(var i=0;i<labels.length;i++)labels[i].textContent=labels[i].getAttribute('data-'+lang);
  document.getElementById('submit').value=lang==='en'?'Sign in':'Войти';
  reveal.textContent=pass.type==='password'?(lang==='en'?'Show':'Показать'):(lang==='en'?'Hide':'Скрыть');
 }
 language.onchange=function(){lang=this.value;try{localStorage.setItem('odi-panel-language',lang);}catch(e){}paint();};
 reveal.onclick=function(){pass.type=pass.type==='password'?'text':'password';reveal.setAttribute('aria-pressed',pass.type==='text'?'true':'false');paint();};
 paint();
})();
</script>
</body></html>
