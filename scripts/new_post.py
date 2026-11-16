#!/usr/bin/env python3
"""Create a complete Markdown draft without ever overwriting a file."""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from content_utils import (
    ROOT, ContentError, dispatch_inventory, exclusive_write, markdown,
    parse_date, repository_lock, slugify, utc_now,
)

WORKS = ['essay', 'poetry', 'short-story', 'reflection']
EVENTS = ['upcoming-event', 'past-event', 'award', 'publication', 'milestone']


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('kind', choices=['dispatch', 'poem', *WORKS, 'event', 'book', 'excerpt'])
    cli.add_argument('title')
    cli.add_argument('--date', default=utc_now(), help='ISO 8601 date or timestamp; naive dates use UTC.')
    cli.add_argument('--body-file', type=Path, help='UTF-8 Markdown body to import.')
    cli.add_argument('--tag', action='append', default=[])
    cli.add_argument('--location', default='')
    cli.add_argument('--organization', default='')
    cli.add_argument('--description', default='')
    cli.add_argument('--synopsis', default='')
    cli.add_argument('--chapter', type=int, default=1)
    cli.add_argument('--event-type', choices=EVENTS, default='upcoming-event')
    cli.add_argument('--publish', action='store_true', help='Create with draft: false.')
    cli.add_argument('--root', type=Path, default=ROOT)
    return cli


def create(args: argparse.Namespace) -> Path:
    title = args.title.strip()
    if not title or len(title) > 180:
        raise ContentError('A title must contain 1–180 characters.')
    timestamp = parse_date(args.date)
    body = args.body_file.read_text(encoding='utf-8') if args.body_file else ''
    if args.publish and not body.strip():
        raise ContentError('--publish requires a nonempty --body-file.')
    if any(not tag.strip() or len(tag.strip()) > 64 for tag in args.tag) or len(args.tag) > 40:
        raise ContentError('Use at most 40 nonempty tags, each at most 64 characters.')
    data = {'title': title, 'date': timestamp.isoformat().replace('+00:00', 'Z'), 'draft': not args.publish}
    root = args.root.resolve()
    with repository_lock(root):
        if args.kind == 'dispatch':
            _, _, highest = dispatch_inventory(root)
            collection = 'dispatches'
            data.update(source='website', dispatchNumber=highest + 1, images=[], imageAlts=[],
                        captionExcerpt='', location=args.location, tags=list(dict.fromkeys(t.strip() for t in args.tag)),
                        featured=False, lockedForManualEdits=True)
        elif args.kind in [*WORKS, 'poem']:
            collection = 'works'
            data.update(category='poetry' if args.kind == 'poem' else args.kind,
                        subtitle='', readingTime=max(1, math.ceil(len(body.split()) / 200)), featured=False)
        elif args.kind == 'event':
            collection = 'events'
            description = args.description.strip() or title
            if len(description) > 2000:
                raise ContentError('Event descriptions must be at most 2,000 characters.')
            data.update(type=args.event_type, location=args.location, organization=args.organization,
                        description=description, photos=[], photoAlts=[])
        else:
            collection = 'book'
            synopsis = args.synopsis.strip() or title
            if len(synopsis) > 5000 or args.chapter < 1:
                raise ContentError('Use a synopsis up to 5,000 characters and a positive chapter number.')
            data.update(kind='overview' if args.kind == 'book' else 'excerpt', synopsis=synopsis,
                        status='gathering-stories', progress=0, thematicPillars=[], order=0)
            if args.kind == 'excerpt':
                data.update(chapterNumber=args.chapter, order=args.chapter)
        destination = root / 'src/content' / collection / f'{timestamp:%Y-%m-%d}-{slugify(title)}.md'
        if not exclusive_write(destination, markdown(data, body).encode('utf-8')):
            raise ContentError(f'File already exists; nothing changed: {destination.name}')
    return destination


def main() -> int:
    args = parser().parse_args()
    try:
        print(create(args))
        return 0
    except (ContentError, OSError) as exc:
        print(f'Cannot create post: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
