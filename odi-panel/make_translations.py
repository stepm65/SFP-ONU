from pathlib import Path
import json
p=Path(__file__).resolve().parent
pairs=[]
for name in ['translations.txt','backend-ru.txt']:
 pairs.extend(line.split('|',1) for line in (p/name).read_text().splitlines() if line.strip())
native=json.loads((p/'native-en.json').read_text())
cn=json.loads((p/'native-cn.json').read_text())
for line in (p/'native-ru.txt').read_text().splitlines():
 n,ru=line.split('|',1);pairs.append([ru,native[int(n)].strip(),cn[int(n)].strip()])
pairs.extend([['Hex (20 символов)','Hex (20 characters)'],['ASCII (10 символов)','ASCII (10 characters)'],['Зарегистрирован','Registered'],['Не зарегистрирован','Unregistered'],['Соединение установлено','Link Up'],['Нет соединения','Link Down'],['Отправлено','Sent'],['Получено','Received'],['Ошибки','Errors'],['Пакеты','Packets'],['Байты','Bytes']])
(p/'src/translations.js').write_text('window.ODITranslations='+json.dumps(pairs,ensure_ascii=False,separators=(',',':'))+';\n')
