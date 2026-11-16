/* Runs synchronously in <head>, before styles paint. No network request required. */
(() => {
  const key = 'yushay-reading-edition';
  if (window.__yushayTheme) {
    window.__yushayTheme.sync();
    return;
  }
  let current = 'light';
  try { current = localStorage.getItem(key) === 'dark' ? 'dark' : 'light'; } catch { /* Storage may be disabled. */ }

  function apply(doc) {
    const dark = current === 'dark';
    doc.documentElement.classList.add('js');
    doc.documentElement.classList.toggle('dark', dark);
    doc.documentElement.dataset.theme = current;
    doc.documentElement.style.colorScheme = current;
    doc.querySelector('meta[name="theme-color"]')?.setAttribute('content', dark ? '#0E0F12' : '#FAF7F2');
    doc.querySelectorAll('[data-theme-toggle]').forEach((button) => button.setAttribute('aria-pressed', String(dark)));
    doc.querySelectorAll('[data-edition-name]').forEach((label) => {
      label.textContent = dark ? 'Nocturne Edition' : 'Warm Literary Press';
    });
  }
  function sync() { apply(document); }
  window.__yushayTheme = { sync };
  sync();
  document.addEventListener('click', (event) => {
    if (!(event.target instanceof Element) || !event.target.closest('[data-theme-toggle]')) return;
    current = current === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem(key, current); } catch { /* The in-memory preference still works. */ }
    sync();
  });
  document.addEventListener('astro:before-swap', (event) => apply(event.newDocument));
  document.addEventListener('astro:page-load', sync);
  document.addEventListener('DOMContentLoaded', sync, { once: true });
  window.addEventListener('storage', (event) => {
    if (event.key !== key && event.key !== null) return;
    current = event.newValue === 'dark' ? 'dark' : 'light';
    sync();
  });
})();
