"""Shared, fail-closed Markdown operations for the author platform."""
from __future__ import annotations

import json
import os
import re
import tempfile
import unicodedata
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterator

import yaml

ROOT = Path(__file__).resolve().parents[1]


class ContentError(ValueError):
    """An input cannot be used without risking editorial content."""


class UniqueKeyLoader(yaml.SafeLoader):
    """Reject duplicate frontmatter keys instead of silently losing values."""


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            raise ContentError('Frontmatter keys must be unique strings.')
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def read_markdown(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding='utf-8')
    match = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)(.*)\Z', text, re.S)
    if not match:
        raise ContentError(f'Missing YAML frontmatter: {path.name}')
    try:
        data = yaml.load(match.group(1), Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise ContentError(f'Invalid YAML frontmatter: {path.name}') from exc
    if not isinstance(data, dict):
        raise ContentError(f'Frontmatter must be a mapping: {path.name}')
    return data, match.group(2)


def markdown(data: dict, body: str) -> str:
    return '---\n' + yaml.safe_dump(data, allow_unicode=True, sort_keys=False) + '---\n\n' + body.rstrip() + '\n'


def slugify(text: str) -> str:
    value = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', value).strip('-')[:72].rstrip('-') or 'untitled'


def parse_date(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, AttributeError) as exc:
        raise ContentError('Dates must use ISO 8601, for example 2026-11-14.') from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def exclusive_write(path: Path, value: bytes) -> bool:
    """Publish a fully written file atomically, without replacing an existing path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp, path)
        except FileExistsError:
            return False
        return True
    finally:
        temp.unlink(missing_ok=True)


def atomic_json(path: Path, data: dict) -> None:
    """The import ledger is machine-owned; editorial Markdown never uses replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.ledger-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


@contextmanager
def repository_lock(root: Path) -> Iterator[None]:
    """OS-managed lock: released on process exit, including after a crash."""
    folder = root / '.cache'
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / 'writer.lock').open('a+b') as handle:
        handle.seek(0)
        handle.write(b'0')
        handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise ContentError('Another publishing process is running.') from exc
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise ContentError('Another publishing process is running.') from exc
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)


def dispatch_inventory(root: Path) -> tuple[dict[str, Path], dict[str, Path], int]:
    ids: dict[str, Path] = {}
    urls: dict[str, Path] = {}
    numbers: set[int] = set()
    highest = 0
    for path in sorted((root / 'src/content/dispatches').rglob('*.md')):
        data, _ = read_markdown(path)
        number = data.get('dispatchNumber')
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise ContentError(f'Invalid dispatchNumber: {path.name}')
        # Launch demonstrations stay available in the local preview without reserving a number.
        is_sample_draft = data.get('draft') is True and path.name.startswith('2026-11-14-sample-')
        if not is_sample_draft:
            if number in numbers:
                raise ContentError(f'Duplicate dispatchNumber: {path.name}')
            numbers.add(number)
            highest = max(highest, number)
        identifier = data.get('instagramId')
        if identifier:
            identifier = str(identifier)
            if not identifier.isdecimal() or identifier in ids:
                raise ContentError(f'Invalid or duplicate instagramId: {path.name}')
            ids[identifier] = path
        match = re.search(r'-ig-(\d+)\.md$', path.name)
        if match:
            identifier = match.group(1)
            if identifier in ids and ids[identifier] != path:
                raise ContentError(f'Duplicate Instagram filename ID: {path.name}')
            ids[identifier] = path
        url = data.get('instagramUrl')
        if url:
            key = str(url).split('?')[0].rstrip('/')
            if key in urls:
                raise ContentError(f'Duplicate Instagram permalink: {path.name}')
            urls[key] = path
    return ids, urls, highest
