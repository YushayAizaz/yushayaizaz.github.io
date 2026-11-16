import { statSync } from 'node:fs';
import { portraitFilename } from './press';

export const portraitPath = `/images/uploads/${portraitFilename}`;

export function hasAuthorPortrait(): boolean {
  const portrait = new URL(portraitPath.slice(1), __EDITORIAL_PUBLIC_DIR_URL__);
  return statSync(portrait, { throwIfNoEntry: false })?.isFile() ?? false;
}
