from pathlib import Path
import sys

root = Path(SPECPATH).parent
a = Analysis([str(root / 'desktop/main.py')], pathex=[str(root)], binaries=[],
             datas=[(str(root / 'desktop/builtin-catalog.json'),'desktop')], hiddenimports=[], hookspath=[], runtime_hooks=[], excludes=[])
if sys.platform == 'win32':
    # Qt 6.12 uses the Windows ICU API. PATH may contain a different ICU build
    # whose version-suffixed exports cannot satisfy QtCore's imports.
    a.binaries = [entry for entry in a.binaries
                  if Path(entry[0]).name.lower() != 'icuuc.dll'
                  and not Path(entry[0]).name.lower().startswith('icudt')]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='SIEANSVision',
          debug=False, strip=False, upx=False, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='SIEANSVision')
