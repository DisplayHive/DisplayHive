#!/usr/bin/env python3
"""Adds the missing `resolved` and `integrity` fields to a package-lock.json.

The Nix package (nix/package.nix) fetches the npm packages itself and needs both for every entry;
npm leaves them out of some lock files (e.g. one written while node_modules already existed).
Versions are not changed — only the two fields are looked up in the registry and added.

    python3 scripts/fill-npm-lock-integrity.py frontends/admin/package-lock.json
"""

import concurrent.futures as cf
import json
import sys
import urllib.request

REGISTRY = 'https://registry.npmjs.org/'


def lookup(item):
    key, name, version = item
    url = REGISTRY + name.replace('/', '%2f') + '/' + version
    error = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                dist = json.load(response)['dist']
            return key, dist['tarball'], dist['integrity']
        except Exception as problem:  # network hiccup: try again
            error = problem
    raise SystemExit(f'{name}@{version}: {error}')


def main(path):
    with open(path, encoding='utf-8') as f:
        lock = json.load(f)
    todo = []
    for key, entry in lock['packages'].items():
        if key and 'node_modules/' in key and not entry.get('link') and ('resolved' not in entry or 'integrity' not in entry):
            name = entry.get('name') or key.rsplit('node_modules/', 1)[1]
            todo.append((key, name, entry['version']))
    with cf.ThreadPoolExecutor(16) as pool:
        found = list(pool.map(lookup, todo))
    for key, tarball, integrity in found:
        entry = {}
        for field, value in lock['packages'][key].items():
            entry[field] = value
            if field == 'version':
                entry['resolved'], entry['integrity'] = tarball, integrity
        lock['packages'][key] = entry
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(lock, f, indent=2, ensure_ascii=False)
        f.write('\n')
    print(f'{path}: filled {len(found)} entries')


if __name__ == '__main__':
    main(sys.argv[1])
