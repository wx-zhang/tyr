import { slides } from './deck.mjs';
const content = document.querySelector('#slide-content');
const overview = document.querySelector('#overview');
const notes = document.querySelector('#notes');
let current = 0;
let request = 0;
function fit() {
  const viewport = document.querySelector('#viewport');
  const scale = Math.min(viewport.clientWidth / 1600, viewport.clientHeight / 900);
  document.querySelector('#stage').style.transform = `scale(${scale})`;
}
function indexFromHash() {
  const value = Number(location.hash.slice(1));
  return Number.isInteger(value) && value >= 1 && value <= slides.length ? value - 1 : 0;
}
async function render() {
  const sequence = ++request;
  current = indexFromHash();
  const index = current;
  try {
    const response = await fetch(`slides/${slides[index][0]}`);
    if (!response.ok) throw new Error(`Couldn't load this slide (${response.status}).`);
    const html = await response.text();
    if (sequence !== request) return;
    content.innerHTML = html;
    const note = content.querySelector('template.notes');
    document.querySelector('#notes-content').replaceChildren(note ? note.content.cloneNode(true) : document.createTextNode('No notes for this slide.'));
    document.querySelector('#notes-title').textContent = `${String(index + 1).padStart(2, '0')} / ${slides[index][1]}`;
    document.querySelector('#slide-count').textContent = `${String(index + 1).padStart(2, '0')} / ${String(slides.length).padStart(2, '0')}`;
    document.querySelector('#section-label').textContent = slides[index][2];
    document.querySelector('#progress').style.width = `${(index + 1) / slides.length * 100}%`;
    document.querySelector('#previous').disabled = index === 0;
    document.querySelector('#next').disabled = index === slides.length - 1;
    document.querySelectorAll('.index-card').forEach((card, i) => card.setAttribute('aria-current', String(i === index)));
    document.title = `${index + 1}. ${slides[index][1]} | Tyr × GAMR`;
  } catch (error) {
    if (sequence !== request) return;
    const message = document.createElement('p');
    message.textContent = error.message;
    content.replaceChildren(message);
  }
}
function go(index) {
  location.hash = String(Math.max(0, Math.min(slides.length - 1, index)) + 1);
}
function toggleDialog(dialog) {
  if (dialog.open) dialog.close();
  else dialog.showModal();
  document.querySelector(`#${dialog.id}-button`).setAttribute('aria-expanded', String(dialog.open));
}
async function fullscreen() {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await document.body.requestFullscreen();
  } catch {
    document.querySelector('#fullscreen').title = 'Fullscreen unavailable in this browser';
  }
}
slides.forEach((slide, index) => {
  const button = document.createElement('button');
  button.className = 'index-card';
  const number = document.createElement('span');
  number.textContent = String(index + 1).padStart(2, '0');
  button.append(number, document.createTextNode(slide[1]));
  button.addEventListener('click', () => { go(index); overview.close(); });
  document.querySelector('#slide-index').append(button);
});
const themeButton = document.querySelector('#theme-button');
function setTheme(theme) {
  const light = theme === 'light';
  document.documentElement.dataset.theme = light ? 'light' : 'dark';
  themeButton.setAttribute('aria-pressed', String(light));
  document.querySelector('meta[name="theme-color"]').content = light ? '#f8fafc' : '#0b0f14';
}
function toggleTheme() {
  const theme = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
  setTheme(theme);
  try { localStorage.setItem('tyr-gamr-deck-theme', theme); } catch {}
}
let savedTheme = 'dark';
try { savedTheme = localStorage.getItem('tyr-gamr-deck-theme') || 'dark'; } catch {}
setTheme(savedTheme);
themeButton.addEventListener('click', toggleTheme);
document.querySelector('#previous').addEventListener('click', () => go(current - 1));
document.querySelector('#next').addEventListener('click', () => go(current + 1));
document.querySelector('#overview-button').addEventListener('click', () => toggleDialog(overview));
document.querySelector('#notes-button').addEventListener('click', () => toggleDialog(notes));
document.querySelector('#fullscreen').addEventListener('click', fullscreen);
document.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => document.getElementById(button.dataset.close).close()));
[overview, notes].forEach(dialog => dialog.addEventListener('close', () => document.querySelector(`#${dialog.id}-button`).setAttribute('aria-expanded', 'false')));
document.addEventListener('keydown', event => {
  if (event.ctrlKey || event.altKey || event.metaKey || event.target.closest('input,textarea,select,[contenteditable]')) return;
  if (overview.open || notes.open) return;
  if (event.key.toLowerCase() === 't') toggleTheme();
  if (event.target.closest('button,a') && [' ', 'Enter'].includes(event.key)) return;
  if (['ArrowRight', 'ArrowDown', 'PageDown', ' '].includes(event.key)) { event.preventDefault(); go(current + 1); }
  if (['ArrowLeft', 'ArrowUp', 'PageUp'].includes(event.key)) { event.preventDefault(); go(current - 1); }
  if (event.key === 'Home') { event.preventDefault(); go(0); }
  if (event.key === 'End') { event.preventDefault(); go(slides.length - 1); }
  if (event.key.toLowerCase() === 'g') toggleDialog(overview);
  if (event.key.toLowerCase() === 'n') toggleDialog(notes);
  if (event.key.toLowerCase() === 'f') fullscreen();
  if (/^[1-9]$/.test(event.key)) go(Number(event.key) - 1);
});
window.addEventListener('hashchange', render);
window.addEventListener('resize', fit);
document.addEventListener('fullscreenchange', () => {
  document.querySelector('#fullscreen').firstChild.textContent = document.fullscreenElement ? 'Exit fullscreen ' : 'Fullscreen ';
  fit();
});
fit();
render();
