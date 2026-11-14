// Share the appearance preference with the chat workspace; never account data.
(() => {
  const key = 'continuum-theme';
  function apply(theme) {
    const mode = theme === 'light' ? 'light' : 'dark';
    document.documentElement.dataset.continuumTheme = mode;
    document.documentElement.classList.toggle('dark', mode === 'dark');
    document.documentElement.style.colorScheme = mode;
    const button = document.getElementById('theme-toggle');
    if (button) {
      button.textContent = mode === 'dark' ? '☀ Light mode' : '☾ Dark mode';
      button.setAttribute('aria-label', mode === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
      button.setAttribute('aria-pressed', String(mode === 'dark'));
    }
    window.dispatchEvent(new CustomEvent('continuum:theme', {detail: mode}));
  }
  let saved;
  try { saved = localStorage.getItem(key); } catch {}
  apply(saved || 'dark');
  document.addEventListener('DOMContentLoaded', () => {
    apply(document.documentElement.dataset.continuumTheme);
    document.getElementById('theme-toggle').addEventListener('click', () => {
      const theme = document.documentElement.dataset.continuumTheme === 'dark' ? 'light' : 'dark';
      apply(theme);
      try { localStorage.setItem(key, theme); } catch {}
    });
  }, {once: true});
  window.addEventListener('storage', event => {
    if (event.key === key || event.key === null) apply(event.newValue || 'dark');
  });
})();
