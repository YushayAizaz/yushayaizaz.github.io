#!/usr/bin/env python3
"""Check cross-entry invariants and local asset references before publication."""
import sys
from pathlib import Path
from content_utils import ROOT, ContentError, dispatch_inventory, read_markdown


def validate(root: Path) -> int:
    dispatch_inventory(root)
    count = 0
    overviews = 0
    chapters = set()
    public = (root / 'public').resolve()
    for collection in ('dispatches', 'works', 'book', 'events'):
        for path in (root / 'src/content' / collection).rglob('*.md'):
            data, _ = read_markdown(path)
            count += 1
            if data.get('draft') is False and collection == 'book':
                overviews += data.get('kind') == 'overview'
                if data.get('kind') == 'excerpt':
                    number = data.get('chapterNumber')
                    if number in chapters:
                        raise ContentError('Published book chapter numbers must be unique.')
                    chapters.add(number)
            for images_key, alts_key in [('images', 'imageAlts'), ('photos', 'photoAlts')]:
                images = data.get(images_key) or []
                alts = data.get(alts_key) or []
                if alts and len(images) != len(alts):
                    raise ContentError(f'{path.name}: image/alt list lengths differ.')
            images = [*(data.get('images') or []), *(data.get('photos') or [])]
            if data.get('coverImage'):
                images.append(data['coverImage'])
            for image in images:
                if not isinstance(image, str) or not image.startswith('/images/'):
                    raise ContentError(f'{path.name}: only local /images/ assets are allowed.')
                target = (public / image.lstrip('/')).resolve()
                if not target.is_relative_to(public) or not target.is_file():
                    raise ContentError(f'{path.name}: an image is missing or outside public/.')
    if overviews > 1:
        raise ContentError('Publish at most one book overview.')
    return count


if __name__ == '__main__':
    try:
        print(f'Validated {validate(ROOT)} content files and their local image references.')
    except (ContentError, OSError) as exc:
        print(f'Content validation failed: {exc}', file=sys.stderr)
        raise SystemExit(1)
