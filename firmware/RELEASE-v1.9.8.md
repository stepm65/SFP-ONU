# ODI Panel 1.9.8 — SFU 240408

Добавлен профиль **Eltex NTU-1 rev.C / bridge**, расширена диагностика потери O5: начало и конец сбора, сброс uptime, штатный таймер перезагрузки, таблицы UNI/bridge/VEIP. Исправлено скрытие `SerialNum` в диагностическом экспорте. Зафиксированы LF для CGI и shell-скриптов.

Профиль использует `OMCI_OLT_MODE=0`, требует отдельного применения и не меняет ваши SN, пароли, MAC и скорость порта. Это стартовая конфигурация для проверки, а не новый режим закрытого OMCI-демона. Работа версии 1.9.8 на реальном стике и Eltex OLT пока не проверена.

- [Образ TAR](ODI-Panel-1.9.8-RU-EN-SFU-240408.tar)
- [SHA256](SHA256SUMS)
- [Изменения и установка](../odi-panel/README-1.9.8.md)
- [Профиль Eltex и сбор диагностики](../odi-panel/docs/05-ELTEX-NTU1-RU.md)
- [Отчёты проверок](reports/1.9.8/)

Для RTL9601D с базой V1.1.8-240408, тегом X100SFP и разделами k0/k1 `0x14c000`, r0/r1 `0x274000`. Перед установкой проверьте базу, разметку и сохраните конфигурацию.

## English

Adds an **Eltex NTU-1 rev.C / bridge** preset using existing OMCI mode 0, with a settings diff before application. It preserves subscriber credentials, identity and port speed. Diagnostics now include UNI/bridge/VEIP tables, start/end PON state and uptime, uptime reset history and a read-only factory reboot timer check. SerialNum redaction and LF handling are corrected.

Version 1.9.8 has software/build validation only. It has not been tested on a physical ONU or Eltex OLT. The preset is a starting configuration, not a new proprietary OMCI implementation or a confirmed fix for O5 disconnects.

Use the TAR above only with the compatible SFU 240408 base and flash layout. Back up the configuration first. Applying the Eltex preset is a separate action after installation.
