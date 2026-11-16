"""Behold feed adapter, import ordering, and non-destructive publication."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, Mock, patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from content_utils import read_markdown
from sync_instagram import (
    BeholdClient, DEFAULT_BEHOLD_FEED_URL, ImageDownloader, SyncError, main, sync,
    validate_cdn_url,
)

CDN = 'https://behold.pictures/fixtures'


def remote_post(post_id, day, **fields):
    return {
        'id': post_id, 'timestamp': f'2026-08-{day:02}T20:00:00+0000',
        'permalink': f'https://www.instagram.com/p/TEST{post_id}/',
        'mediaType': 'IMAGE', 'mediaUrl': f'{CDN}/{post_id}.webp',
        'caption': f'Dispatch {post_id} #original', **fields,
    }


def response(payload=None, image=None):
    result = Mock()
    result.status_code = 200
    result.headers = {'Content-Type': 'image/webp'} if image else {}
    result.json.return_value = payload
    result.iter_content.return_value = [image] if image else []
    manager = MagicMock()
    manager.__enter__.return_value = result
    return manager


class BeholdSyncTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.client = BeholdClient(DEFAULT_BEHOLD_FEED_URL)
        self.addCleanup(self.client.close)
        self.downloader = ImageDownloader()
        self.addCleanup(self.downloader.close)
        pixels = io.BytesIO()
        Image.new('RGB', (3, 3), '#c69d82').save(pixels, format='WEBP')
        self.image = pixels.getvalue()

    def test_oldest_first_clean_captions_complete_carousels_and_editorial_lock(self):
        raw = 'https://scontent.cdninstagram.com/post-100-first.jpg'
        posts = [
            remote_post('300', 21, mediaType='CAROUSEL_ALBUM', children=[
                {'id': '301', 'mediaType': 'IMAGE', 'mediaUrl': CDN + '/301.webp'},
            ]),
            remote_post('200', 17, mediaType='VIDEO', mediaUrl=CDN + '/200.mp4',
                        thumbnailUrl=CDN + '/200-poster.webp'),
            remote_post('100', 16, mediaType='CAROUSEL_ALBUM', mediaUrl=raw + '?sign=cover',
                        prunedCaption='A patient beginning.\n\nThese are the words.', hashtags=['#Listening', 'listening', 'Budapest'],
                        children=[
                            {'id': '101', 'mediaType': 'IMAGE', 'mediaUrl': raw + '?sign=slide',
                             'sizes': {'large': {'mediaUrl': CDN + '/101.webp'}}},
                            {'id': '102', 'mediaType': 'VIDEO', 'mediaUrl': CDN + '/102.mp4',
                             'sizes': {'large': {'mediaUrl': CDN + '/102-poster.webp'}}},
                        ]),
        ]
        expected_images = ['101.webp', '102-poster.webp', '200-poster.webp', '300.webp', '301.webp']

        def fetch(_session, url, **_kwargs):
            if url == DEFAULT_BEHOLD_FEED_URL:
                return response({'posts': posts})
            self.assertIn(url, [f'{CDN}/{name}' for name in expected_images])
            return response(image=self.image)

        with patch('sync_instagram.request', side_effect=fetch) as requests:
            self.assertEqual(sync(self.root, self.client, self.downloader, feature_latest=True),
                             {'imported': 3, 'skipped': 0, 'planned': 0})
            self.assertEqual([call.args[1] for call in requests.call_args_list],
                             [DEFAULT_BEHOLD_FEED_URL, *(f'{CDN}/{name}' for name in expected_images)])

        articles = sorted((self.root / 'src/content/dispatches').glob('*.md'))
        parsed = [read_markdown(path) for path in articles]
        self.assertEqual([data['dispatchNumber'] for data, _ in parsed], [1, 2, 3])
        self.assertEqual([data['featured'] for data, _ in parsed], [False, False, True])
        self.assertTrue(all(data['draft'] is False and data['lockedForManualEdits'] for data, _ in parsed))
        self.assertEqual([len(data['images']) for data, _ in parsed], [2, 1, 2])
        self.assertEqual(parsed[0][0]['tags'], ['listening', 'budapest'])
        self.assertIn('These are the words.', parsed[0][1].replace(r'\.', '.'))
        self.assertNotIn('original', parsed[0][1])
        self.assertNotIn('#original', parsed[1][1])
        for data, _ in parsed:
            for url in data['images']:
                self.assertTrue(url.startswith(f"/images/dispatches/{data['instagramId']}/"))
                self.assertEqual((self.root / 'public' / url.lstrip('/')).read_bytes(), self.image)

        articles[0].write_text(articles[0].read_text() + '\nMy edited paragraph.\n', encoding='utf-8')
        articles[1].unlink()  # The ledger tombstone must survive feed reappearance.
        original = articles[0].read_bytes()
        ledger = self.root / 'data/instagram-imports.json'
        self.assertEqual(set(json.loads(ledger.read_bytes())['posts']), {'100', '200', '300'})
        original_ledger = ledger.read_bytes()
        with patch('sync_instagram.request', side_effect=fetch) as requests:
            self.assertEqual(sync(self.root, self.client, self.downloader, feature_latest=True)['skipped'], 3)
            self.assertEqual(requests.call_count, 1)
        self.assertEqual(articles[0].read_bytes(), original)
        self.assertFalse(articles[1].exists())
        self.assertEqual(ledger.read_bytes(), original_ledger)

    def test_missing_carousel_children_does_not_publish_incomplete_entry(self):
        with patch('sync_instagram.request', return_value=response({'posts': [
            remote_post('123', 16, mediaType='CAROUSEL_ALBUM', children=[]),
        ]})):
            with self.assertRaisesRegex(SyncError, 'no valid children'):
                sync(self.root, self.client, self.downloader)
        self.assertFalse((self.root / 'src/content/dispatches').exists())
        self.assertFalse((self.root / 'data/instagram-imports.json').exists())

    def test_untrusted_hosts_are_rejected(self):
        for url in ['http://feeds.behold.so/test', 'https://feeds.behold.so.evil.invalid/test',
                    'https://evil@feeds.behold.so/test', 'https://feeds.behold.so:444/test']:
            with self.subTest(url=url), self.assertRaises(SyncError):
                BeholdClient(url)
        validate_cdn_url(CDN + '/slide.webp')
        with self.assertRaises(SyncError):
            validate_cdn_url('https://behold.pictures.evil.invalid/slide.webp')

    def test_cli_uses_configured_behold_feed_when_token_is_absent(self):
        override = 'https://feeds.behold.so/custom-feed'
        for env, expected in [({}, DEFAULT_BEHOLD_FEED_URL), ({'BEHOLD_FEED_URL': override}, override)]:
            with self.subTest(env=env), patch.dict(os.environ, env, clear=True), \
                    patch.object(sys, 'argv', ['sync_instagram.py', '--root', str(self.root), '--dry-run']), \
                    patch('sync_instagram.BeholdClient') as behold, patch('sync_instagram.sync', return_value={}), \
                    patch('builtins.print'):
                self.assertEqual(main(), 0)
                behold.assert_called_once_with(expected)

    def test_cli_prefers_instagram_login_when_token_is_supplied(self):
        with patch.dict(os.environ, {'INSTAGRAM_ACCESS_TOKEN': 'test-token', 'INSTAGRAM_USER_ID': '123'}, clear=True), \
                patch.object(sys, 'argv', ['sync_instagram.py', '--root', str(self.root), '--dry-run']), \
                patch('sync_instagram.InstagramClient') as instagram, patch('sync_instagram.sync', return_value={}), \
                patch('builtins.print'):
            self.assertEqual(main(), 0)
            instagram.assert_called_once_with('test-token', '123', 'v27.0')


if __name__ == '__main__':
    unittest.main()
