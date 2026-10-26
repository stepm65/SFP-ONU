from pathlib import Path
import hashlib,json,zipfile,sys
p=Path(__file__).resolve().parent;root=p.parent
from release import VERSION, sync_sources
sync_sources(check=True)
# Regenerate previews from current sources; do not package stale snapshots.
import runpy
runpy.run_path(str(p/'make_preview.py'))
archive=root/f'ODI-Panel-{VERSION}-RU-EN-SFU-240408.zip'
build=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else root/f'release-{VERSION}-sfu'
report=json.loads((build/'build-report.json').read_text())
assert report['panel_version']==VERSION and report['base_tag']=='SFU-240408'
image=next(build.glob('*.tar'))
reports=root/'firmware/reports'/VERSION
validation=json.loads((reports/'validation-scope.json').read_text())
assert validation['firmware_sha256']==hashlib.sha256(image.read_bytes()).hexdigest()
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 z.write(image,image.name);checksum=hashlib.sha256(image.read_bytes()).hexdigest()+'  '+image.name
 z.write(p/f'README-{VERSION}.md','README-RU.md')
 z.write(p/'preview.html','preview.html');z.write(p/'login-preview.html','login-preview.html')
 for f in sorted((p/'docs').glob('*.md')):z.write(f,'docs/'+f.name)
 for f in sorted((p/'src').rglob('*')):
  if f.is_file():z.write(f,'source/src/'+f.relative_to(p/'src').as_posix())
 for f in sorted((p/'upstream').rglob('*')):
  if f.is_file() and not (f.parent.name=='odi-tools' and f.suffix!='.json'):z.write(f,'source/upstream/'+f.relative_to(p/'upstream').as_posix())
 for f in sorted(p.iterdir()):
  if f.is_file() and f.name!='patch_build.py' and (f.suffix in ['.py','.cjs','.txt'] or f.name=='VERSION' or f.name in ['native-en.json','native-cn.json','native-preview.json']):z.write(f,'source/'+f.name)
 for n in ['patch_boa.py','test_patch.py','test_unicorn.py']:z.write(p/'hotfix'/n,'source/hotfix/'+n)
 # Only evidence collected for this release; do not reuse historical test claims.
 for f in sorted(reports.glob('*.json')):z.write(f,'reports/'+f.name)
 z.writestr('SHA256SUMS',checksum+'\n')
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'image':image.name,'sha256':checksum.split()[0],'rootfs_bytes':report['rootfs_bytes'],'free_rootfs_bytes':report['rootfs_limit']-report['rootfs_bytes']},indent=2))
