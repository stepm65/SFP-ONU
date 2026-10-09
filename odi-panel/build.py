#!/usr/bin/env python3
"""Build ODI Panel on the exact, reviewed ODI SFU 240408 image.
python3 build.py BASE.tar SQUASHFS_TOOLS OUTPUT
Run from anywhere; src/ is resolved beside this file. Never flashes hardware.
"""
import hashlib,io,json,re,shlex,struct,subprocess,sys,tarfile,zlib
from pathlib import Path
PROJECT=Path(__file__).resolve().parent
from release import VERSION, sync_sources
sync_sources(check=True)
base,tools,out=map(lambda p:Path(p).resolve(),sys.argv[1:])
out.mkdir(parents=True,exist_ok=False)
sha=lambda b:hashlib.sha256(b).hexdigest()
BASES={
 '79c5ce4e62f4cb334b4335ad405d14f8c905b8b61d56ca636486d1ef91632623':{'tag':'SFU-240408','version':'V1.1.8-240408'}
}
base_sha=sha(base.read_bytes());assert base_sha in BASES,'Unexpected base: only the reviewed ODI SFU 240408 TAR is supported'
profile=BASES[base_sha]
def run(*args):
 p=subprocess.run(list(map(str,args)),capture_output=True)
 if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
 return p.stdout
names=['fwu.sh','rootfs','uImage','fwu_ver','hw_ver','md5.txt']
with tarfile.open(base) as t:
 assert sorted(t.getnames())==sorted(names)
 data={n:t.extractfile(n).read() for n in names};meta={n:t.getmember(n) for n in names}
for l in data['md5.txt'].decode().splitlines():
 digest,n=l.split();assert hashlib.md5(data[n.lstrip('*')]).hexdigest()==digest
assert data['hw_ver']==b'X100SFP\n' and data['fwu_ver'].decode().strip()==profile['version']
tar_changes=[]
assert hashlib.md5(data['fwu.sh']).hexdigest()=='aff0174cbba7b029b61259777f3d7196'
kernel=data['uImage'];kh=bytearray(kernel[:64]);assert struct.unpack_from('>I',kh)[0]==0x27051956
crc=struct.unpack_from('>I',kh,4)[0];kh[4:8]=b'\0'*4;assert zlib.crc32(kh)==crc
assert struct.unpack_from('>I',kernel,12)[0]+64==len(kernel)
assert zlib.crc32(kernel[64:])==struct.unpack_from('>I',kernel,24)[0]
sb=data['rootfs'][:96];assert sb[:4]==b'hsqs' and struct.unpack_from('<H',sb,20)[0]==2
block=struct.unpack_from('<I',sb,12)[0];epoch=struct.unpack_from('<I',sb,8)[0]
(out/'rootfs.original').write_bytes(data['rootfs'])
run(tools/'unsquashfs','-no-progress','-pf',out/'original.pseudo',out/'rootfs.original')
MARK=b'#\n# START OF DATA - DO NOT MODIFY\n#\n'
def read_pseudo(path):
 header,blob=path.read_bytes().split(MARK,1)
 entries={}
 for line in header.decode().splitlines():
  a=shlex.split(line,comments=True)
  if not a:continue
  item={'fields':a[1:],'line':line}
  if a[1]=='R':
   length,offset=map(int,a[6:8]);payload=blob[offset:offset+length];assert len(payload)==length
   item['data']=payload;item['compare']=a[1:6]+[sha(payload)]
  else:item['compare']=a[1:]
  entries[a[0]]=item
 return entries,blob
before,blob=read_pseudo(out/'original.pseudo')
from hotfix.patch_boa import patch as patch_boa
boa_binary,boa_patch_report=patch_boa(before['bin/boa']['data'])
mods={'bin/boa':boa_binary}
(out/'boa-patch-report.json').write_text(json.dumps(boa_patch_report,indent=2)+'\n')
for n in ['index.html','panel.css','panel.js','api.cgi','upload.cgi','translations.js','i18n.js','native-menu.js','native.js','native.css','mods.js','mackey.js','ploam.js','firmware.js','diagnostics.js','profiles.js','ux.js','layout.js']:
 mods['home/httpd/web/panel/'+n]=(PROJECT/'src'/n).read_bytes()
for n in ['odi-mods-lib.sh','odi-mods-run.sh','odi-diagnostics.sh']:
 mods['etc/scripts/'+n]=(PROJECT/'src'/n).read_bytes()
for n in ['fix_speed.sh','fix_sw_ver.sh','fix_vlan_tag.sh','fix_vlan_fwdop.sh']:
 mods['etc/scripts/'+n]=(PROJECT/'src/anime'/n).read_bytes()
mods['etc/scripts/odi-panel-boot.sh']=(PROJECT/'src/odi-panel-boot.sh').read_bytes()
mods['home/httpd/web/legacy.html']=before['home/httpd/web/index.html']['data']
mods['home/httpd/web/index.html']=b'<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=/panel/index.html"><title>ODI Panel</title></head><body><a href="/panel/index.html">ODI Panel</a> | <a href="/legacy.html">Original interface</a></body></html>\n'
conf=before['home/httpd/boa.conf']['data'].decode()
assert 'Auth / /var/boaSuper.passwd' in conf
conf+='\n# ODI Panel: CGI inherits administrator authentication; no new listener.\nAddType application/x-httpd-cgi cgi\nAddType text/css css\nAuth /panel /var/boaSuper.passwd\n'
mods['home/httpd/boa.conf']=conf.encode()
rc=before['etc/init.d/rc3']['data'].decode();assert rc.count('/etc/insdrv.sh')==1
mods['etc/init.d/rc3']=rc.replace('/etc/insdrv.sh','/etc/insdrv.sh\n/etc/scripts/odi-panel-boot.sh').replace('/etc/runlansds.sh','/etc/runlansds.sh\n/etc/scripts/odi-mods-run.sh >/dev/null 2>&1 &').encode()
# Theme and translate original ASP pages while retaining every form and ASP handler.
native_injection=(f'<link rel="stylesheet" href="/panel/native.css?v={VERSION}"><script src="/panel/translations.js?v={VERSION}"></script><script src="/panel/i18n.js?v={VERSION}"></script><script src="/panel/native.js?v={VERSION}"></script>').encode()
native_pages=[]
for name,item in before.items():
 if name.startswith('home/httpd/web/') and name.endswith('.asp') and 'data' in item:
  original=item['data']
  if re.search(br'<head\b[^>]*>',original,re.I) and name.rsplit('/',1)[-1] not in ['code.asp','code_user.asp','title.asp','logobelow.asp']:
   patched=re.sub(br'(<head\b[^>]*>)',lambda m:m[0]+native_injection,original,count=1,flags=re.I)
   # Factory GPON page refers to two commented-out controls. Guard those lookups.
   if name=='home/httpd/web/gpon.asp':
    patched=patched.replace(b'if (document.formOmciInfo.oui.value=="")',b'if (document.formOmciInfo.oui && document.formOmciInfo.oui.value=="")')
    patched=patched.replace(b'omcc_ver.value = omcc_ver_value;',b'if(typeof omcc_ver !== "undefined") omcc_ver.value = omcc_ver_value;')
   mods[name]=patched;native_pages.append(name)

# Login must render before authentication: inline styling and language controls.
login=(PROJECT/'src/login-template.asp').read_text()
for route in ['admin/login.asp','login.asp']:
 captcha='<div class="field"><label for="captcha" data-en="Verification code">Код с картинки</label><div class="captcha"><input id="captcha" name="captcha" maxlength="30" autocomplete="off"><img src="/captcha.gif" width="100" height="30" alt="CAPTCHA"></div></div>' if route=='login.asp' else ''
 mods['home/httpd/web/'+route]=login.replace('<!-- CAPTCHA -->',captcha).encode()

mods['home/httpd/web/saveconf.asp']=(PROJECT/'src/saveconf.asp').read_bytes()
# Remove only replaced file definitions; original byte offsets stay valid.
header='\n'.join(item['line'] for name,item in before.items() if name not in mods)+'\n'
(out/'patched.pseudo').write_bytes(header.encode()+MARK+blob)
(out/'empty').mkdir();(out/'overlay').mkdir()
root=before['/']['fields']
args=[tools/'mksquashfs',out/'empty',out/'rootfs','-comp','lzma','-b',str(block),'-always-use-fragments','-no-xattrs','-noappend','-no-sparse','-nopad','-processors','1','-mkfs-time',str(epoch),'-root-time',root[1],'-root-mode',root[2],'-root-uid',root[3],'-root-gid',root[4],'-pf',out/'patched.pseudo','-p',f'home/httpd/web/panel D {epoch} 755 0 0']
for i,(name,content) in enumerate(mods.items()):
 p=out/'overlay'/str(i);p.write_bytes(content)
 if name in before:
  old=before[name]['fields'];assert old[0]=='R'
  timestamp,mode,uid,gid=old[1:5]
 else:timestamp,mode,uid,gid=str(epoch),('755' if name.endswith(('.cgi','.sh')) else '644'),'0','0'
 args+=['-p',f'{name} F {timestamp} {mode} {uid} {gid} cat {shlex.quote(str(p))}']
run(*args)
run(tools/'unsquashfs','-no-progress','-pf',out/'verified.pseudo',out/'rootfs')
after,_=read_pseudo(out/'verified.pseudo')
assert set(after)==set(before)|set(mods)|{'home/httpd/web/panel'}
for name,item in before.items():
 if name not in mods:assert after[name]['compare']==item['compare'],name
for name,content in mods.items():
 assert after[name]['data']==content,name
 if name in before:assert after[name]['fields'][:5]==before[name]['fields'][:5],name
 else:assert after[name]['fields'][3:5]==['0','0'],name
assert after['home/httpd/web/panel']['fields']==['D',str(epoch),'755','0','0']
data['rootfs']=(out/'rootfs').read_bytes()
assert len(kernel)<=0x14c000 and len(data['rootfs'])<=0x274000
assert struct.unpack_from('<H',data['rootfs'],20)[0]==2 and struct.unpack_from('<I',data['rootfs'],12)[0]==block
data['md5.txt']=''.join(hashlib.md5(data[n]).hexdigest()+'  '+n+'\n' for n in names if n!='md5.txt').encode()
firmware=out/('ODI-Panel-'+VERSION+'-RU-EN-'+profile['tag']+'.tar')
with tarfile.open(firmware,'w',format=tarfile.USTAR_FORMAT) as t:
 for n in names:
  m=meta[n];m.size=len(data[n]);t.addfile(m,io.BytesIO(data[n]))
with tarfile.open(firmware) as t:
 for n in names:assert t.extractfile(n).read()==data[n]
report={'base_sha256':base_sha,'firmware_sha256':sha(firmware.read_bytes()),'base_version':profile['version'],'base_tag':profile['tag'],'panel_version':VERSION,'tar_changes':tar_changes,'kernel_sha256':sha(kernel),'native_pages_themed':len(native_pages),'kernel_bytes':len(kernel),'kernel_limit':0x14c000,'rootfs_bytes':len(data['rootfs']),'rootfs_limit':0x274000,'lzma_block_bytes':block,'modified_files':[n for n in mods if n in before],'added_files':[n for n in mods if n not in before],'preserved_entries':sum(n not in mods for n in before),'checks':['source MD5/SHA256','kernel header/payload CRC32','size bounds','full SquashFS content and metadata comparison','final TAR contents/MD5']}
(out/'build-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
