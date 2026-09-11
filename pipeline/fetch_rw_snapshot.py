"""Freeze one RW GitLab commit and verify its CSV against repository metadata."""

import argparse
import io
import json
from pathlib import Path
import re
import tarfile
import urllib.request

from .validate_snapshot import atomic_bytes, atomic_json, digest, now


API = 'https://gitlab.com/api/v4/projects/crossref%2Fretraction-watch-data/repository'


def fetch(commit, output):
    if not re.fullmatch('[a-f0-9]{40}', commit):
        raise ValueError('Use a full immutable Git commit SHA')
    output = Path(output).resolve()
    repository = Path(__file__).resolve().parents[1]
    if output.is_relative_to(repository) and not output.is_relative_to(repository / 'data/raw'):
        raise ValueError('RW raw files must be external or in ignored data/raw')
    with urllib.request.urlopen(API + '/commits/' + commit, timeout=60) as response:
        metadata = json.load(response)
    raw_url = API + '/files/retraction_watch.csv/raw?ref=' + commit
    with urllib.request.urlopen(urllib.request.Request(raw_url, method='HEAD'), timeout=60) as response:
        expected_hash = response.headers['X-Gitlab-Content-Sha256']
    url = API + '/archive.tar.gz?sha=' + commit + '&path=retraction_watch.csv'
    with urllib.request.urlopen(url, timeout=120) as response:
        archive = response.read()
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as source:
        members = [member for member in source.getmembers() if member.isfile() and member.name.endswith('/retraction_watch.csv')]
        if len(members) != 1:
            raise ValueError('Archive must contain exactly one RW CSV')
        raw = source.extractfile(members[0]).read()
    if digest(raw) != expected_hash:
        raise ValueError('RW CSV differs from pinned GitLab content hash')
    atomic_bytes(output / 'retraction_watch.csv', raw)
    atomic_json(output / 'source.json', {'rw_source_commit': commit,
        'rw_snapshot_date': metadata['committed_date'][:10], 'rw_csv_sha256': digest(raw),
        'retrieved_at': now(), 'url': url})
    print('Frozen RW input: ' + str(output))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    fetch(args.commit, args.output_dir)
