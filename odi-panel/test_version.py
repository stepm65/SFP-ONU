"""Check the release consumers and actual firmware overlays, including both logins."""
from pathlib import Path
import json, re, sys
from release import VERSION, sync_sources

P=Path(__file__).resolve().parent
sync_sources(check=True)
checks=[]

def page_version(text,label):
    footer=re.search(r'<footer\b[^>]*>(.*?)</footer>',text,re.S)[1]
    assert re.findall(r'ODI Panel (\d+\.\d+\.\d+)',footer)==[VERSION],label
    assert f'name="odi-panel-version" content="{VERSION}"' in text,label
    checks.append(label)

for name in ['src/index.html','src/login-template.asp','preview.html','login-preview.html']:
    page_version((P/name).read_text(),name)
index=(P/'src/index.html').read_text()
assert set(re.findall(r'\?v=([^"\s]+)',index))=={VERSION}
assert 'emit panel_version "$PANEL_VERSION"' in (P/'src/odi-diagnostics.sh').read_text()
assert f'PANEL_VERSION={VERSION}\n' in (P/'src/api.cgi').read_text()
assert "state.panel_version||'1.7.0'" not in (P/'src/profiles.js').read_text()
checks.append('asset URLs, diagnostic version and profile source')

for directory in sys.argv[1:]:
    build=Path(directory)
    assert json.loads((build/'build-report.json').read_text())['panel_version']==VERSION
    raw=(build/'verified.pseudo').read_bytes()
    header,blob=raw.split(b'#\n# START OF DATA - DO NOT MODIFY\n#\n',1)
    import shlex
    files={}
    for line in header.decode().splitlines():
        row=shlex.split(line,comments=True)
        if len(row)>1 and row[1]=='R':
            length,offset=map(int,row[6:8]);files[row[0]]=blob[offset:offset+length]
    for path in ['home/httpd/web/admin/login.asp','home/httpd/web/login.asp','home/httpd/web/panel/index.html']:
        page_version(files[path].decode(),build.name+': '+path)
    assert f'PANEL_VERSION={VERSION}\n'.encode() in files['home/httpd/web/panel/api.cgi']
    assert b'emit panel_version "$PANEL_VERSION"' in files['etc/scripts/odi-diagnostics.sh']
    checks.append(build.name+': API and diagnostics')
    native=files['home/httpd/web/tcpiplan.asp'].decode()
    for asset in ['native.css','translations.js','i18n.js','native.js']:
        assert f'/panel/{asset}?v={VERSION}' in native,(build.name,asset)
    checks.append(build.name+': versioned native LAN assets')

(P/'version-test-report.json').write_text(json.dumps({'result':'passed','version':VERSION,'checks':checks},indent=2)+'\n')
print(f'Version {VERSION}: {len(checks)} consistency checks passed')
