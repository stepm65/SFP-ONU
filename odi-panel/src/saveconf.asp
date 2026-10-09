<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Обслуживание устройства</title><link rel="stylesheet" href="/panel/native.css"><script src="/panel/translations.js"></script><script src="/panel/i18n.js"></script><script src="/panel/native.js"></script>
<script>
function uploadClick(){if(!document.saveConfig.binary.value){alert('Выберите файл резервной копии.');return false;}return confirm('Восстановить настройки из выбранного файла? Текущая конфигурация будет заменена.');}
function resetClick(all){return confirm(all?'Сбросить все параметры? Настройки подключения к оператору будут удалены.':'Сбросить настройки с сохранением критических параметров? Состав сохраняемых параметров определяет штатная прошивка.');}
</script></head><body class="maintenance-page">
<header class="maintenance-heading"><h1>Обслуживание устройства</h1><p>Сохраните копию перед восстановлением или сбросом настроек.</p></header>
<form action="/boaform/formSaveConfig" method="POST" name="saveCSConfig" class="maintenance-card">
 <div class="maintenance-description"><h2>Резервная копия</h2><p>Скачайте текущую конфигурацию и сохраните файл на компьютере.</p></div>
 <div class="maintenance-controls"><button type="submit" name="save_cs" value="<% multilang("495" "LANG_BACKUP"); %>...">Скачать копию</button></div>
</form>
<form action="/boaform/formSaveConfig" enctype="multipart/form-data" method="POST" name="saveConfig" class="maintenance-card" onsubmit="return uploadClick()">
 <div class="maintenance-description"><h2>Восстановление из файла</h2><p>Выберите ранее сохранённую конфигурацию. Восстановление заменит текущие настройки.</p></div>
 <div class="maintenance-controls restore-controls"><label for="backup-file">Файл резервной копии</label><input id="backup-file" type="file" name="binary" required><button type="submit" name="load" value="<% multilang("497" "LANG_RESTORE"); %>" class="secondary">Восстановить настройки</button></div>
 <input type="hidden" name="submit-url" value="/saveconf.asp">
</form>
<form action="/boaform/admin/formOmciInfo" method="POST" name="fiberResetConfig" class="maintenance-card">
<div class="maintenance-description"><h2>Fiber Reset</h2><p>Сброс настроек после 5–6 отключений и подключений оптики за 30 секунд. Состав сохраняемых параметров определяет штатная прошивка.</p><p>Кнопка сохраняет состояние функции и не запускает сброс.</p></div>
<div class="maintenance-controls restore-controls"><label for="fiberreset">Сброс переподключением оптики</label><select id="fiberreset" name="fiberreset"><option value="0">Выключено</option><option value="1">Включено</option></select><button name="apply" type="submit" value="<% multilang("146" "LANG_APPLY_CHANGES"); %>">Сохранить</button></div>
<input type="hidden" name="submit-url" value="/saveconf.asp">
<div hidden id="fiber-current"><input type="radio" name="fiber_readonly" value="0" disabled <% checkWrite("fiber-reset0"); %>><input type="radio" name="fiber_readonly" value="1" disabled <% checkWrite("fiber-reset1"); %>></div>
</form>
<form action="/boaform/formSaveConfig" method="POST" name="resetConfig" class="reset-group">
 <section class="maintenance-card"><div class="maintenance-description"><h2>Сброс с сохранением критических параметров</h2><p>Вернуть обычные настройки к значениям по умолчанию. Какие параметры сохраняются, определяет штатная прошивка.</p></div><div class="maintenance-controls"><button type="submit" name="reset" value="<% multilang("210" "LANG_RESET"); %>" class="secondary" onclick="return resetClick(false)">Сбросить настройки</button></div></section>
 <section class="maintenance-card danger-card"><div class="maintenance-description"><span class="danger-label">Удаление конфигурации</span><h2>Полный сброс</h2><p>Удалить все параметры, включая настройки подключения к оператору. После сброса потребуется повторная настройка.</p></div><div class="maintenance-controls"><button type="submit" name="reset0" value="<% multilang("210" "LANG_RESET"); %>" class="danger" onclick="return resetClick(true)">Сбросить всё</button></div></section>
 <input type="hidden" name="submit-url" value="/saveconf.asp">
</form>
<script>document.addEventListener('DOMContentLoaded',function(){var current=document.querySelector('#fiber-current input:checked');var select=document.getElementById('fiberreset');if(current){select.value=current.value;}else{select.disabled=true;document.querySelector('[name=fiberResetConfig] button').disabled=true;}});</script>
</body></html>
