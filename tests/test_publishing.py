"""Behavioral regression tests for editorial preservation and import integrity."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests
import yaml
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from content_utils import ContentError, exclusive_write, markdown, read_markdown
from new_post import create, parser
from sync_instagram import (
    ImageDownloader, InstagramClient, SyncError, caption_metadata, import_post,
    plain_caption_markdown, request, sync, validate_cdn_url,
)
from validate_content import validate


def post(post_id='123', media_type='IMAGE', caption='An evening: a beginning.\n\nHuman stories. #Budapest #Listening'):
    return {'id': post_id, 'media_type': media_type, 'caption': caption,
            'timestamp': '2026-11-14T18:00:00+0000',
            'permalink': f'https://www.instagram.com/p/EXAMPLE{post_id}/',
            'media_url': 'https://scontent.cdninstagram.com/a.jpg',
            'thumbnail_url': 'https://scontent.cdninstagram.com/poster.jpg'}


class FakeClient:
    def __init__(self, records=None, children=None):
        self.records = records if records is not None else [post()]
        self.album = children if children is not None else [post('456'), post('789')]
        self.child_calls = 0

    def media(self, max_pages):
        return iter(self.records)

    def children(self, post_id, max_pages):
        self.child_calls += 1
        return self.album


class FakeDownloader:
    def __init__(self, fail_at=0):
        self.calls = 0
        self.fail_at = fail_at

    def download(self, url, staging, stem):
        self.calls += 1
        if self.calls == self.fail_at:
            raise SyncError('Simulated image download failure.')
        path = staging / f'{stem}.jpg'
        Image.new('RGB', (3, 3), (100, 80, 60)).save(path)
        return path


class Response:
    def __init__(self, status=200, payload=None, content=b'', headers=None):
        self.status_code = status
        self.payload = payload
        self.content = content
        self.headers = headers or {'Content-Type': 'image/png'}

    def json(self):
        return self.payload

    def iter_content(self, size):
        yield self.content

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class PublishingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'src/content/dispatches').mkdir(parents=True)
        self.client = FakeClient()
        self.downloader = FakeDownloader()

    def tearDown(self):
        self.temp.cleanup()

    def files(self):
        return list((self.root / 'src/content/dispatches').glob('*.md'))

    def test_first_import_local_images_and_defaults(self):
        result = sync(self.root, self.client, self.downloader)
        self.assertEqual(result['imported'], 1)
        data, body = read_markdown(self.files()[0])
        self.assertTrue(data['lockedForManualEdits'])
        self.assertFalse(data['draft'])
        self.assertEqual(data['dispatchNumber'], 1)
        self.assertEqual(data['tags'], ['budapest', 'listening'])
        self.assertTrue(data['images'][0].startswith('/images/dispatches/123/'))
        self.assertTrue((self.root / 'public' / data['images'][0].lstrip('/')).is_file())
        self.assertIn('Human stories', body)
        self.assertEqual(validate(self.root), 1)

    def test_first_import_ignores_unpublished_demo_number_and_preserves_source(self):
        demo = self.root / 'src/content/dispatches/2026-11-14-sample-evening-notebook.md'
        demo.write_text(markdown({'title': 'Sample', 'dispatchNumber': 1, 'draft': True}, 'Preview text.'))
        original = demo.read_bytes()

        self.assertEqual(sync(self.root, self.client, self.downloader)['imported'], 1)
        article = next(path for path in self.files() if path != demo)
        self.assertEqual(read_markdown(article)[0]['dispatchNumber'], 1)
        self.assertEqual(validate(self.root), 2)
        self.assertEqual(sync(self.root, self.client, self.downloader)['skipped'], 1)
        self.assertEqual(demo.read_bytes(), original)

    def test_published_demo_and_non_demo_drafts_still_reserve_dispatch_numbers(self):
        for filename, number, draft in [
            ('2026-11-14-sample-published.md', 3, False),
            ('2026-11-15-new-draft.md', 4, True),
        ]:
            path = self.root / 'src/content/dispatches' / filename
            path.write_text(markdown({'title': 'Note', 'dispatchNumber': number, 'draft': draft}, 'Draft text.'))
        self.assertEqual(sync(self.root, self.client, self.downloader)['imported'], 1)
        article = next(path for path in self.files() if '-ig-' in path.name)
        self.assertEqual(read_markdown(article)[0]['dispatchNumber'], 5)

    def test_existing_bytes_untouched_even_when_lock_is_false(self):
        sync(self.root, self.client, self.downloader)
        path = self.files()[0]
        data, _ = read_markdown(path)
        data.update(title='My director’s cut', tags=['personal'], lockedForManualEdits=False)
        path.write_text(markdown(data, 'My expanded essay.\n\nA second paragraph.'), encoding='utf-8')
        original = path.read_bytes()
        (self.root / 'data/instagram-imports.json').unlink()
        self.client.records[0]['caption'] = 'A remotely revised caption #changed'
        sync(self.root, self.client, self.downloader)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(self.downloader.calls, 1)

    def test_locked_file_and_changed_slug_are_preserved(self):
        sync(self.root, self.client, self.downloader)
        path = self.files()[0]
        original = path.read_bytes()
        renamed = path.with_name('completely-renamed.md')
        path.rename(renamed)
        (self.root / 'data/instagram-imports.json').unlink()
        sync(self.root, self.client, self.downloader)
        self.assertEqual(self.files(), [renamed])
        self.assertEqual(renamed.read_bytes(), original)

    def test_deleted_post_not_resurrected(self):
        sync(self.root, self.client, self.downloader)
        self.files()[0].unlink()
        result = sync(self.root, self.client, self.downloader)
        self.assertEqual(result['skipped'], 1)
        self.assertEqual(self.files(), [])

    def test_carousel_downloads_every_child(self):
        self.client.records = [post(media_type='CAROUSEL_ALBUM')]
        sync(self.root, self.client, self.downloader)
        data, _ = read_markdown(self.files()[0])
        self.assertEqual(len(data['images']), 2)
        self.assertEqual(self.downloader.calls, 2)

    def test_video_and_mixed_carousel_store_posters(self):
        self.client.records = [post(media_type='CAROUSEL_ALBUM')]
        self.client.album = [post('456'), post('789', 'VIDEO')]
        sync(self.root, self.client, self.downloader)
        data, _ = read_markdown(self.files()[0])
        self.assertEqual(len(data['images']), 2)

    def test_failed_second_image_never_publishes_partial_markdown(self):
        self.client.records = [post(media_type='CAROUSEL_ALBUM')]
        with self.assertRaises(SyncError):
            sync(self.root, self.client, FakeDownloader(fail_at=2))
        self.assertEqual(self.files(), [])
        self.assertFalse((self.root / 'data/instagram-imports.json').exists())
        self.assertFalse((self.root / 'public/images/dispatches/123').exists())

    def test_missing_media_url_fails_closed(self):
        self.client.records[0].pop('media_url')
        with self.assertRaises(SyncError):
            sync(self.root, self.client, self.downloader)
        self.assertEqual(self.files(), [])

    def test_dry_run_creates_nothing(self):
        before = sorted(str(p) for p in self.root.rglob('*'))
        result = sync(self.root, self.client, self.downloader, dry_run=True)
        self.assertEqual(result['planned'], 1)
        self.assertEqual(before, sorted(str(p) for p in self.root.rglob('*')))
        self.assertEqual(self.downloader.calls, 0)

    def test_repeat_sync_has_no_content_or_ledger_changes(self):
        sync(self.root, self.client, self.downloader)
        originals = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        sync(self.root, self.client, self.downloader)
        self.assertEqual(originals, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_broken_frontmatter_blocks_import(self):
        (self.root / 'src/content/dispatches/editor.md').write_text('An unfinished manual edit')
        with self.assertRaises(ContentError):
            sync(self.root, self.client, self.downloader)
        self.assertEqual(self.downloader.calls, 0)

    def test_broken_ledger_blocks_import(self):
        (self.root / 'data').mkdir()
        (self.root / 'data/instagram-imports.json').write_text('{')
        with self.assertRaises(ContentError):
            sync(self.root, self.client, self.downloader)

    def test_duplicate_ids_in_remote_pages_import_once(self):
        self.client.records = [post(), post()]
        sync(self.root, self.client, self.downloader)
        self.assertEqual(len(self.files()), 1)
        self.assertEqual(self.downloader.calls, 1)

    def test_exclusive_write_never_replaces(self):
        path = self.root / 'draft.md'
        self.assertTrue(exclusive_write(path, b'original'))
        self.assertFalse(exclusive_write(path, b'changed'))
        self.assertEqual(path.read_bytes(), b'original')

    def test_existing_exact_target_is_never_touched(self):
        sync(self.root, self.client, self.downloader)
        path = self.files()[0]
        original = path.read_bytes()
        self.assertIsNone(import_post(self.root, post(), 2, self.client, self.downloader, 200, False))
        self.assertEqual(path.read_bytes(), original)

    def test_cli_creates_all_kinds_as_valid_drafts(self):
        for kind in ['dispatch', 'poem', 'essay', 'reflection', 'short-story', 'event', 'book', 'excerpt']:
            args = parser().parse_args([kind, f'A new {kind}', '--root', str(self.root)])
            path = create(args)
            data, _ = read_markdown(path)
            self.assertTrue(data['draft'])
        self.assertEqual(validate(self.root), 8)

    def test_cli_refuses_duplicate_and_empty_publication(self):
        args = parser().parse_args(['dispatch', 'My dispatch', '--root', str(self.root)])
        path = create(args)
        original = path.read_bytes()
        with self.assertRaises(ContentError):
            create(args)
        self.assertEqual(path.read_bytes(), original)
        args = parser().parse_args(['essay', 'Empty', '--publish', '--root', str(self.root)])
        with self.assertRaises(ContentError):
            create(args)

    def test_caption_plaintext_cannot_inject_html(self):
        body = plain_caption_markdown('<script>alert(1)</script>\n![x](javascript:alert(1))')
        self.assertNotIn('<script>', body)
        self.assertNotIn('![x]', body)
        title, excerpt, tags = caption_metadata('#Budapest #Budapest', '123')
        self.assertEqual(title, 'Evening Dispatch 123')
        self.assertEqual(tags, ['budapest'])
        self.assertEqual(excerpt, '')

    def test_cdn_host_validation(self):
        for url in ['http://scontent.cdninstagram.com/a.jpg', 'https://cdninstagram.com.evil.test/x',
                    'https://127.0.0.1/x', 'https://evil.test/x', 'https://user:pass@cdninstagram.com/x']:
            with self.assertRaises(SyncError):
                validate_cdn_url(url)
        validate_cdn_url('https://scontent.cdninstagram.com/a.jpg')

    def test_api_paginates_without_following_tokenized_next_url(self):
        client = InstagramClient('secret', '123', 'v27.0')
        with patch.object(client, 'page', side_effect=[
            {'data': [post('1')], 'paging': {'next': 'https://evil.test/?access_token=secret', 'cursors': {'after': 'cursor'}}},
            {'data': [post('2')]},
        ]) as page:
            self.assertEqual(len(list(client.media(10))), 2)
            self.assertEqual(page.call_args.args[1]['after'], 'cursor')
        client.close()

    def test_child_edge_pagination(self):
        client = InstagramClient('secret', '123', 'v27.0')
        with patch.object(client, 'page', side_effect=[
            {'data': [post('1')], 'paging': {'next': 'ignored', 'cursors': {'after': 'cursor'}}},
            {'data': [post('2')]},
        ]):
            self.assertEqual(len(client.children('123', 10)), 2)
        client.close()

    def test_pagination_limit_is_not_silent_truncation(self):
        client = InstagramClient('secret', '123', 'v27.0')
        with patch.object(client, 'page', return_value={
            'data': [post()], 'paging': {'next': 'ignored', 'cursors': {'after': 'again'}},
        }):
            with self.assertRaises(SyncError):
                list(client.media(1))
        client.close()

    def test_rate_limit_retries(self):
        with requests.Session() as session, patch.object(session, 'get', side_effect=[Response(429), Response(200)]) as get, patch('sync_instagram.time.sleep'):
            result = request(session, 'https://graph.instagram.com/v27.0/123/media')
            self.assertEqual(result.status_code, 200)
            self.assertEqual(get.call_count, 2)

    def test_bad_download_never_creates_asset(self):
        downloader = ImageDownloader()
        with patch('sync_instagram.request', return_value=Response(content=b'not an image')):
            with self.assertRaises(SyncError):
                downloader.download('https://scontent.cdninstagram.com/a.png', self.root, 'asset')
        self.assertFalse((self.root / 'asset.png').exists())
        downloader.close()

    def test_verified_download_uses_actual_image_format(self):
        output = io.BytesIO()
        Image.new('RGB', (3, 3)).save(output, format='PNG')
        downloader = ImageDownloader()
        with patch('sync_instagram.request', return_value=Response(content=output.getvalue())):
            path = downloader.download('https://scontent.cdninstagram.com/wrong.jpg', self.root, 'asset')
        self.assertEqual(path.suffix, '.png')
        downloader.close()

    def test_cms_includes_all_schema_fields(self):
        project = Path(__file__).resolve().parents[1]
        config = yaml.safe_load((project / '.pages.yml').read_text())
        self.assertEqual({c['name'] for c in config['content']}, {'dispatches', 'works', 'book', 'events'})
        for collection in config['content']:
            names = {field['name'] for field in collection['fields']}
            for file in (project / collection['path']).glob('*.md'):
                data, _ = read_markdown(file)
                self.assertTrue(set(data).issubset(names), file.name)
            self.assertIn('body', names)
            self.assertIn('draft', names)


if __name__ == '__main__':
    unittest.main()
