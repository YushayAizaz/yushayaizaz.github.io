export function bindBioCopy(
  button: HTMLButtonElement,
  bio: HTMLElement,
  status: HTMLElement,
  clipboard?: Pick<Clipboard, 'writeText'>,
) {
  let active = true;
  let pending = false;
  let clearStatus: ReturnType<typeof setTimeout> | undefined;

  async function copy() {
    if (pending) return;
    pending = true;
    clearTimeout(clearStatus);
    status.textContent = '';
    try {
      if (!clipboard) throw new Error('Clipboard unavailable');
      await clipboard.writeText((bio.textContent ?? '').trim());
      if (!active) return;
      status.textContent = 'Copied to clipboard';
      clearStatus = setTimeout(() => { status.textContent = ''; }, 2500);
    } catch {
      if (active) status.textContent = 'Clipboard unavailable. Select the bio text to copy it.';
    } finally {
      pending = false;
    }
  }

  button.addEventListener('click', copy);
  button.hidden = false;
  return () => {
    active = false;
    clearTimeout(clearStatus);
    button.removeEventListener('click', copy);
    status.textContent = '';
    button.hidden = true;
  };
}
