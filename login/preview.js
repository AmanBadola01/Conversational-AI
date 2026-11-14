const toggle = document.getElementById('chk');
function setMode(mode) {
  toggle.checked = mode === 'login';
  document.querySelectorAll('.switch').forEach(button => button.setAttribute('aria-expanded', String(button.dataset.mode === mode)));
  document.querySelectorAll('form').forEach(form => {
    const active = form.id === `${mode}-form`;
    form.querySelectorAll('input,button[type=submit]').forEach(input => { input.disabled = !active; });
    form.querySelector('.status').textContent = '';
  });
}
document.querySelectorAll('.switch').forEach(button => button.addEventListener('click', () => setMode(button.dataset.mode)));
document.querySelectorAll('form').forEach(form => {
  let pending = false;
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (pending || !form.reportValidity()) return;
    const signup = form.id === 'signup-form';
    const data = {email: form.elements.email.value.trim(), password: form.elements.password.value};
    if (signup) { data.username = form.elements.username.value.trim(); data.profile_number = form.elements.broj.value; }
    const button = form.querySelector('[type=submit]'), status = form.querySelector('.status');
    pending = true; button.disabled = true; status.textContent = 'Please wait…';
    try {
      const response = await fetch(`/api/auth/${signup ? 'register' : 'login'}`, {
        method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)
      });
      const body = await response.json();
      if (!response.ok) throw new Error(Array.isArray(body.detail) ? body.detail.map(e => e.msg).join('. ') : body.detail || 'Unable to sign in.');
      form.reset();
      if (window.parent !== window) window.parent.postMessage({type: 'continuum:authenticated'}, window.location.origin);
      else window.location.assign('/');
    } catch (error) { status.textContent = error.message || 'Connection failed. Please try again.'; }
    finally { pending = false; button.disabled = false; form.elements.password.value = ''; }
  });
  form.addEventListener('input', () => { form.querySelector('.status').textContent = ''; });
});
setMode('login');
