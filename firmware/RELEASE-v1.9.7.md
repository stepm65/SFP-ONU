# ODI Panel 1.9.7 — SFU 240408

**Русский** · [English](#english)

Веб-панель управления для GPON ONU SFP-стиков на **Realtek RTL9601D**, проверена на **ODI DFP-34X-2IY2**, на заводской основе **ODI SFU V1.1.8-240408**. Полное описание возможностей и скриншоты — в [README](https://github.com/stepm65/sfp-onu#readme).

> Перед установкой сохраните резервную копию конфигурации. Панель пишет прошивку только в неработающий банк, поэтому к прежней версии всегда можно вернуться.

## Прошивка

`ODI-Panel-1.9.7-RU-EN-SFU-240408.tar`
SHA256: `4adb90b7c11c822d0d7a8094974aa268d69d9fc06c49ccc1d1c73225a3818e6c`

Для стиков на RTL9601D с заводской основой V1.1.8-240408 (метка X100SFP) и разметкой k0/r0/k1/r1; перед установкой на другую модель сверьте версию и разметку (см. README). Загружайте TAR, не ZIP.

## Установка

- **Заводская прошивка 240408:** загрузите TAR через штатную страницу «Обновление прошивки».
- **Установленная панель:** «Прошивка» → текущий банк для следующей загрузки → загрузите TAR в другой банк → дождитесь проверки → выберите новый банк и перезагрузите.
- Затем откройте `/panel/index.html` и нажмите Ctrl+F5: должны отображаться панель **1.9.7** и основа **V1.1.8-240408**.

## Возможности

- Состояние PON (O1–O7) и оптика по DDM: RX/TX, температура, напряжение, ток лазера; компактный и диагностический режимы.
- LOID, GPON SN, PLOAM в HEX или ASCII, профиль OMCI, пользовательские версии ПО, расчёт MACKEY в браузере.
- VLAN, режим SFP-порта 1G/2,5G, встроенные штатные страницы LAN/IP.
- Диагностика PON/OMCI с выгрузкой без паролей, моды Anime4000, перенос профиля с рабочего ONU, резервные копии.
- Установка прошивки в неактивный банк с проверкой до и после записи.
- Интерфейс на русском и английском, работает на телефоне.

---

<a id="english"></a>
## English

Web panel for GPON ONU SFP sticks on the **Realtek RTL9601D**, tested on the **ODI DFP-34X-2IY2**, on the factory base **ODI SFU V1.1.8-240408**. Full feature list and screenshots: [README (English)](https://github.com/stepm65/sfp-onu/blob/main/README.en.md).

> Back up your configuration before installing. The panel only writes firmware to the bank that is not running, so you can always go back to the previous version.

### Firmware

`ODI-Panel-1.9.7-RU-EN-SFU-240408.tar`
SHA256: `4adb90b7c11c822d0d7a8094974aa268d69d9fc06c49ccc1d1c73225a3818e6c`

For RTL9601D sticks with the factory V1.1.8-240408 base (tag X100SFP) and the k0/r0/k1/r1 layout; check the version and layout before installing on another model (see README). Upload the TAR, not a ZIP.

### Installation

- **Factory firmware 240408:** upload the TAR on the factory "Firmware Upgrade" page.
- **Installed panel:** Firmware → select the running bank for the next boot → upload the TAR to the other bank → wait for verification → select the new bank and reboot.
- Then open `/panel/index.html` and press Ctrl+F5: panel **1.9.7** and base **V1.1.8-240408** should be shown.

### Features

- PON status (O1–O7) and DDM optics: RX/TX, temperature, voltage, laser bias; compact and diagnostic modes.
- LOID, GPON SN, PLOAM in HEX or ASCII, OMCI profile, custom software versions, in-browser MACKEY calculation.
- VLAN, SFP port mode 1G/2.5G, embedded factory LAN/IP pages.
- PON/OMCI diagnostics with secret-free export, Anime4000 mods, profile transfer from a working ONU, backups.
- Firmware installation into the inactive bank with checks before and after writing.
- English and Russian interface, works on a phone.
