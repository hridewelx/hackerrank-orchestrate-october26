#!/usr/bin/env python3
"""Build a deterministic source archive with an explicit file allowlist."""
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[1]
ALLOWED={'.py','.md','.txt'}

def package(root=ROOT):
    files=[root/'README.md',root/'requirements.txt']
    files+=sorted(p for p in (root/'code').rglob('*') if p.is_file() and p.suffix in ALLOWED and '__pycache__' not in p.parts)
    files+=sorted((root/'docs').glob('*.md'))
    for required in ['code/evaluation/evaluation_report.md','code/evaluation/usage_report.md']:
        if root/required not in files:raise ValueError(f'Missing required report: {required}')
    with zipfile.ZipFile(root/'code.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(files):
            name=p.relative_to(root).as_posix()
            if any(part.startswith('.') for part in Path(name).parts):raise ValueError('Hidden file in package')
            info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.external_attr=0o100644<<16;info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,p.read_bytes())
            if name in {'code/evaluation/evaluation_report.md','code/evaluation/usage_report.md'}:
                alias=zipfile.ZipInfo(name.removeprefix('code/'),(2026,1,1,0,0,0));alias.external_attr=0o100644<<16;alias.compress_type=zipfile.ZIP_DEFLATED
                z.writestr(alias,p.read_bytes())
    with zipfile.ZipFile(root/'code.zip') as z:
        assert not any(n.startswith(('dataset/','.venv/','.cache/')) or n.endswith(('.zip','.json','.jsonl')) for n in z.namelist())
        print(f'{root / "code.zip"}: {len(z.namelist())} source/documentation files, {sum(i.file_size for i in z.infolist())} uncompressed bytes')
if __name__=='__main__':package()
