export const author = {
  name: 'Yushay Aizaz',
  handle: '@yushayaizaz',
  instagram: 'https://www.instagram.com/yushayaizaz/',
  threads: 'https://www.threads.net/@yushayaizaz',
  description: 'Field dispatches, original writing, and a book in progress. Yushay Aizaz writes about human connection and the quiet complexity of an inner life.',
};

export const navigation = [
  { label: 'The dispatches', href: '/dispatches/' },
  { label: 'Original works', href: '/works/' },
  { label: 'The book', href: '/book/' },
  { label: 'The ledger', href: '/achievements/' },
];

export const bookStatuses: Record<string, string> = {
  'gathering-stories': 'Gathering stories',
  drafting: 'Writing the manuscript',
  revising: 'In revision',
  'seeking-publication': 'Seeking publication',
  published: 'Published',
};
