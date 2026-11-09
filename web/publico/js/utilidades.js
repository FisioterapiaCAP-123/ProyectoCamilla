export const porId = (id) => document.getElementById(id);

export function signo(n) { return n > 0 ? 1 : (n < 0 ? -1 : 0); }
export function conSigno(n) { return (n > 0 ? '+' : '') + n; }

/* Texto de usuarios dentro de HTML: nunca se pega sin escapar */
const ENTIDADES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export function esc(texto) {
  return String(texto == null ? '' : texto).replace(/[&<>"']/g, (c) => ENTIDADES[c]);
}

export function sinTildes(texto) {
  return String(texto).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}
