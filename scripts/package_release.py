#!/usr/bin/env python3
"""Package a clean committed source snapshot, without runtime or private files."""
import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()

    def git(*arguments):
        return subprocess.check_output(['git', '-C', str(root), *arguments]).decode()

    if git('status', '--porcelain').strip():
        raise SystemExit('Commit source changes before packaging a release snapshot.')
    files = [name for name in git('ls-files', '-z').split('\0') if name]
    for name in files:
        path = Path(name)
        if any(part in {'.git', '.next', 'node_modules', '__pycache__', '.venv'} for part in path.parts):
            raise SystemExit(f'Refusing runtime/generated file: {name}')
        if path.suffix in {'.sqlite3', '.pyc', '.pem', '.key'} or (path.name.startswith('.env') and 'example' not in path.name):
            raise SystemExit(f'Refusing private/runtime file: {name}')
        if (root / path).is_symlink():
            raise SystemExit(f'Review symlink before packaging: {name}')
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = []
    snapshot = {'commit': git('rev-parse', 'HEAD').strip(),
                'branch': git('branch', '--show-current').strip(),
                'source_files': len(files), 'acceptance': 'staging candidate; live commerce not accepted'}
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in files:
            raw = (root / name).read_bytes()
            manifest.append(f'{hashlib.sha256(raw).hexdigest()}  {name}')
            archive.write(root / name, f'ShoppingWebsite/{name}')
        archive.writestr('ShoppingWebsite/SHA256SUMS.txt', '\n'.join(manifest) + '\n')
        archive.writestr('ShoppingWebsite/SOURCE_SNAPSHOT.json', json.dumps(snapshot, indent=2) + '\n')
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise SystemExit('ZIP integrity check failed.')
        for row in manifest:
            digest, name = row.split('  ', 1)
            if hashlib.sha256(archive.read(f'ShoppingWebsite/{name}')).hexdigest() != digest:
                raise SystemExit('Source hash verification failed.')
    print(json.dumps({'path': str(output), 'bytes': output.stat().st_size, **snapshot,
                      'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                      'validation': 'ZIP CRC and all source hashes passed'}))


if __name__ == '__main__':
    main()
