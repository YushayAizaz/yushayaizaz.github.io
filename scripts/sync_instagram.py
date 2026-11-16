#!/usr/bin/env python3
"""Import new Instagram posts only; preserve every existing editorial byte.

Uses Instagram API with Instagram Login, not the retired Basic Display API.
Credentials are read only from environment variables. Never log request URLs,
response bodies, access tokens, or captions. Images are staged and verified before
any Markdown is created. An import ledger preserves deletion/rename decisions.
"""
from __future__ import annotations

import argparse
import html
import io
import json
import os
import re
import sys
import tempfile
import time
import warnings
from contextlib import nullcontext
from pathlib import Path
from urllib.parse import urlsplit

import requests
from PIL import Image, UnidentifiedImageError

from content_utils import (
    ROOT, ContentError, atomic_json, dispatch_inventory, exclusive_write,
    markdown, parse_date, repository_lock, slugify, utc_now,
)

MAX_BYTES = 30 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 50_000_000
FORMATS = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp', 'GIF': '.gif', 'AVIF': '.avif'}
HASHTAG = re.compile(r'(?<!\w)#([^\W\d]\w*)', re.UNICODE)


class SyncError(RuntimeError):
    """Safe-to-log error; contains no URLs, tokens or remote response text."""


def identifier(value: object) -> str:
    result = str(value or '')
    if not re.fullmatch(r'[0-9]{1,40}', result):
        raise SyncError('API returned an invalid media ID.')
    return result


def request(session, url: str, **kwargs):
    for attempt in range(4):
        try:
            response = session.get(url, timeout=(10, 60), allow_redirects=False, **kwargs)
        except requests.RequestException:
            if attempt == 3:
                raise SyncError('Network request failed after four attempts.') from None
            time.sleep(min(2 ** attempt, 30))
            continue
        if response.status_code == 429 or response.status_code >= 500:
            retry = response.headers.get('Retry-After', '')
            delay = min(int(retry), 30) if retry.isdigit() else min(2 ** attempt, 30)
            response.close()
            if attempt == 3:
                raise SyncError('Remote service is rate limited or unavailable after four attempts.')
            time.sleep(delay)
            continue
        return response
    raise SyncError('Request retry budget exhausted.')


class InstagramClient:
    def __init__(self, token: str, user_id: str, version: str):
        if not token.strip() or not re.fullmatch(r'\d+', user_id):
            raise SyncError('Set INSTAGRAM_ACCESS_TOKEN and the numeric INSTAGRAM_USER_ID.')
        if not re.fullmatch(r'v\d+\.\d+', version):
            raise SyncError('INSTAGRAM_API_VERSION must look like v27.0.')
        self.user_id = user_id
        self.base = f'https://graph.instagram.com/{version}'
        self.session = requests.Session()
        self.session.headers.update({'Authorization': f'Bearer {token}', 'User-Agent': 'YushayJournalSync/1.0'})

    def close(self):
        self.session.close()

    def page(self, edge: str, params: dict) -> dict:
        with request(self.session, f'{self.base}/{edge}', params=params) as response:
            try:
                payload = response.json()
            except ValueError:
                raise SyncError('Instagram returned invalid JSON.') from None
            if not isinstance(payload, dict):
                raise SyncError('Instagram returned an unexpected payload.')
            if response.status_code != 200 or 'error' in payload:
                error = payload.get('error')
                code = error.get('code') if isinstance(error, dict) else None
                if code == 190:
                    raise SyncError('Instagram authorization expired or was revoked; replace the repository token secret.')
                safe_code = str(code) if isinstance(code, int) else 'unknown'
                raise SyncError(f'Instagram request failed (HTTP {response.status_code}, code {safe_code}).')
            return payload

    def paginate(self, edge: str, fields: str, max_pages: int):
        after = None
        seen = set()
        for _ in range(max_pages):
            params = {'fields': fields, 'limit': 100}
            if after:
                params['after'] = after
            payload = self.page(edge, params)
            data = payload.get('data')
            if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
                raise SyncError('Instagram returned a malformed media list.')
            yield from data
            paging = payload.get('paging') or {}
            if not paging.get('next'):
                return
            after = (paging.get('cursors') or {}).get('after')
            if not isinstance(after, str) or not after or after in seen:
                raise SyncError('Invalid or repeated pagination cursor; refusing a partial archive.')
            seen.add(after)
        raise SyncError('Pagination limit reached; increase --max-pages for this archive.')

    def media(self, max_pages: int):
        return self.paginate(f'{self.user_id}/media', 'id,caption,media_type,media_url,thumbnail_url,permalink,timestamp', max_pages)

    def children(self, post_id: str, max_pages: int):
        return list(self.paginate(f'{identifier(post_id)}/children', 'id,media_type,media_url,thumbnail_url', max_pages))


def validate_cdn_url(url: str) -> None:
    try:
        parts = urlsplit(url)
        host = parts.hostname or ''
        port = parts.port
    except (ValueError, TypeError):
        raise SyncError('Invalid image URL.') from None
    allowed = any(host == domain or host.endswith('.' + domain)
                  for domain in ('cdninstagram.com', 'fbcdn.net', 'instagram.com'))
    if parts.scheme != 'https' or not allowed or port not in (None, 443) or parts.username or parts.password:
        raise SyncError('Image URL is not an approved HTTPS Instagram CDN host.')


class ImageDownloader:
    def __init__(self):
        # Separate session: the Graph authorization header never reaches the CDN.
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'YushayJournalSync/1.0'

    def close(self):
        self.session.close()

    def download(self, url: str, staging: Path, stem: str) -> Path:
        for hop in range(4):
            validate_cdn_url(url)
            with request(self.session, url, stream=True) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    url = response.headers.get('Location', '')
                    if hop == 3:
                        raise SyncError('Image redirect limit exceeded.')
                    continue
                if response.status_code != 200:
                    raise SyncError(f'Image download failed (HTTP {response.status_code}).')
                if not response.headers.get('Content-Type', '').lower().startswith('image/'):
                    raise SyncError('CDN response was not an image.')
                length = response.headers.get('Content-Length', '')
                if length.isdigit() and int(length) > MAX_BYTES:
                    raise SyncError('Image exceeded the 30 MiB safety limit.')
                content = bytearray()
                try:
                    for chunk in response.iter_content(64 * 1024):
                        content.extend(chunk)
                        if len(content) > MAX_BYTES:
                            raise SyncError('Image exceeded the 30 MiB safety limit.')
                except requests.RequestException:
                    raise SyncError('Image transfer was interrupted; no Markdown was created.') from None
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter('error', Image.DecompressionBombWarning)
                        with Image.open(io.BytesIO(content)) as picture:
                            extension = FORMATS.get(picture.format)
                            picture.verify()
                        if not extension:
                            raise SyncError('Unsupported image format.')
                except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
                    raise SyncError('Image failed integrity or dimension checks.') from None
                destination = staging / f'{stem}{extension}'
                destination.write_bytes(content)
                return destination
        raise SyncError('Image could not be downloaded.')


def caption_metadata(caption: str, post_id: str) -> tuple[str, str, list[str]]:
    tags = list(dict.fromkeys(tag.casefold()[:64] for tag in HASHTAG.findall(caption)))[:40]
    cleaned = HASHTAG.sub('', caption).strip()
    first_line = next((line.strip() for line in cleaned.splitlines() if line.strip()), '')
    title = first_line or f'Evening Dispatch {post_id}'
    if len(title) > 100:
        cut = title[:97].rsplit(' ', 1)[0]
        title = (cut or title[:97]) + '…'
    excerpt = re.sub(r'\s+', ' ', cleaned).strip()
    if len(excerpt) > 320:
        excerpt = excerpt[:317].rsplit(' ', 1)[0] + '…'
    return title, excerpt, tags


def plain_caption_markdown(caption: str) -> str:
    # Captions are plain text, not executable HTML or authored Markdown.
    escaped = html.escape(caption, quote=False)
    escaped = re.sub(r'([\\`*_{}\[\]()#+.!|>~\-])', r'\\\1', escaped)
    return '\n'.join(line + '  ' if line.strip() else '' for line in escaped.splitlines()).strip()


def read_ledger(root: Path) -> dict:
    path = root / 'data/instagram-imports.json'
    if not path.exists():
        return {'version': 1, 'posts': {}}
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, OSError):
        raise ContentError('Unreadable import ledger; restore it before syncing.') from None
    if not isinstance(value, dict) or value.get('version') != 1 or not isinstance(value.get('posts'), dict):
        raise ContentError('Unsupported import ledger format.')
    for key, item in value['posts'].items():
        if not re.fullmatch(r'\d+', key) or not isinstance(item, dict) or not isinstance(item.get('path'), str):
            raise ContentError('Malformed import ledger entry.')
    return value


def import_post(root: Path, post: dict, number: int, client, downloader, max_pages: int, draft: bool) -> Path | None:
    post_id = identifier(post.get('id'))
    caption = post.get('caption') or ''
    if not isinstance(caption, str):
        raise SyncError('Invalid caption type.')
    title, excerpt, tags = caption_metadata(caption, post_id)
    timestamp = parse_date(post.get('timestamp', ''))
    permalink = post.get('permalink', '')
    if not isinstance(permalink, str) or not re.fullmatch(r'https://(?:www\.)?instagram\.com/(?:p|reel|tv)/[A-Za-z0-9_-]+/?', permalink):
        raise SyncError('Instagram returned an invalid permalink.')
    path = root / 'src/content/dispatches' / f'{timestamp:%Y-%m-%d}-{slugify(title)}-ig-{post_id}.md'
    if path.exists():
        return None
    media_type = post.get('media_type')
    if media_type == 'CAROUSEL_ALBUM':
        items = client.children(post_id, max_pages)
        if not items:
            raise SyncError('Carousel has no accessible children; refusing an incomplete import.')
    elif media_type in ('IMAGE', 'VIDEO'):
        items = [post]
    else:
        raise SyncError('Unsupported Instagram media type.')
    seen = set()
    urls = []
    for item in items:
        child_id = identifier(item.get('id'))
        if child_id in seen:
            continue
        seen.add(child_id)
        if item.get('media_type') == 'IMAGE':
            url = item.get('media_url')
        elif item.get('media_type') == 'VIDEO':
            # The literary reader stores a poster; playback remains on Instagram.
            url = item.get('thumbnail_url')
        else:
            raise SyncError('Unsupported carousel child media type.')
        if not isinstance(url, str) or not url:
            raise SyncError('An image or video poster is unavailable; refusing a partial import.')
        urls.append((child_id, url))
    cache = root / '.cache'
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='instagram-', dir=cache) as directory:
        staging = Path(directory)
        staged = [downloader.download(url, staging, f'{index:02d}-{child_id}')
                  for index, (child_id, url) in enumerate(urls, start=1)]
        public_dir = root / 'public/images/dispatches' / post_id
        local_paths = []
        for image in staged:
            target = public_dir / image.name
            # A previous interrupted import may have left an identical asset.
            if not exclusive_write(target, image.read_bytes()) and target.read_bytes() != image.read_bytes():
                raise SyncError('Existing image differs; preserving it and refusing to publish this import.')
            local_paths.append('/' + target.relative_to(root / 'public').as_posix())
        data = {
            'title': title, 'dispatchNumber': number,
            'date': timestamp.isoformat().replace('+00:00', 'Z'),
            'source': 'instagram', 'instagramId': post_id, 'instagramUrl': permalink,
            'images': local_paths, 'imageAlts': [''] * len(local_paths),
            'captionExcerpt': excerpt, 'location': '', 'tags': tags,
            'featured': False, 'draft': draft, 'lockedForManualEdits': True,
        }
        if not exclusive_write(path, markdown(data, plain_caption_markdown(caption)).encode('utf-8')):
            return None
    return path


def sync(root: Path, client, downloader, *, max_pages=200, draft=False, dry_run=False) -> dict:
    ids, urls, highest = dispatch_inventory(root)
    ledger = read_ledger(root)
    before = json.dumps(ledger, sort_keys=True)
    # Recover identity after a crash between Markdown publication and ledger write.
    for post_id, path in ids.items():
        ledger['posts'].setdefault(post_id, {'path': path.relative_to(root).as_posix()})
    records = list(client.media(max_pages))
    records.sort(key=lambda item: (parse_date(item.get('timestamp', '')), identifier(item.get('id'))))
    imported = skipped = planned = 0
    seen = set()
    for post in records:
        post_id = identifier(post.get('id'))
        if post_id in seen:
            continue
        seen.add(post_id)
        permalink = str(post.get('permalink', '')).split('?')[0].rstrip('/')
        if post_id in ledger['posts'] or post_id in ids or permalink in urls:
            skipped += 1
            if permalink in urls:
                ledger['posts'].setdefault(post_id, {'path': urls[permalink].relative_to(root).as_posix()})
            continue
        if dry_run:
            planned += 1
            continue
        path = import_post(root, post, highest + 1, client, downloader, max_pages, draft)
        if path is None:
            skipped += 1
            continue
        highest += 1
        imported += 1
        ledger['posts'][post_id] = {'path': path.relative_to(root).as_posix(), 'importedAt': utc_now()}
        atomic_json(root / 'data/instagram-imports.json', ledger)
    if not dry_run and json.dumps(ledger, sort_keys=True) != before:
        atomic_json(root / 'data/instagram-imports.json', ledger)
    return {'imported': imported, 'skipped': skipped, 'planned': planned}


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--root', type=Path, default=ROOT)
    cli.add_argument('--max-pages', type=int, default=200)
    cli.add_argument('--dry-run', action='store_true', help='Read-only inventory; do not download images or write files.')
    args = cli.parse_args()
    client = downloader = None
    try:
        if args.max_pages < 1:
            raise ContentError('--max-pages must be positive.')
        draft_value = os.getenv('INSTAGRAM_IMPORT_DRAFT', 'false').lower()
        if draft_value not in ('true', 'false'):
            raise ContentError('INSTAGRAM_IMPORT_DRAFT must be true or false.')
        client = InstagramClient(os.getenv('INSTAGRAM_ACCESS_TOKEN', ''), os.getenv('INSTAGRAM_USER_ID', ''),
                                 os.getenv('INSTAGRAM_API_VERSION', 'v27.0'))
        downloader = ImageDownloader()
        context = nullcontext() if args.dry_run else repository_lock(args.root.resolve())
        with context:
            summary = sync(args.root.resolve(), client, downloader, max_pages=args.max_pages,
                           draft=draft_value == 'true', dry_run=args.dry_run)
        print(json.dumps(summary, sort_keys=True))
        return 0
    except (SyncError, ContentError) as exc:
        print(f'Instagram sync stopped: {exc}', file=sys.stderr)
        return 1
    except Exception as exc:
        # Exception messages may embed a signed CDN URL or request credentials.
        print(f'Instagram sync stopped ({type(exc).__name__}); no remote details logged.', file=sys.stderr)
        return 1
    finally:
        if client:
            client.close()
        if downloader:
            downloader.close()


if __name__ == '__main__':
    raise SystemExit(main())
