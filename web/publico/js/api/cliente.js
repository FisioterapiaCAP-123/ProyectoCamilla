/* Peticiones HTTP al servidor de la Raspberry (web/servidor.py).

   El token de la sesion (lo da /api/login) va en la cabecera X-Sesion y se
   guarda en sessionStorage: cada pestana cuenta como un dispositivo y al
   recargar la pagina no hay que volver a entrar. */
import { sesion } from '../estado.js';
import { registrar } from '../ui/registro.js';

const API_BASE = '';   // '' porque la pagina la sirve la misma Raspberry
const LLAVE_TOKEN = 'sesion';

try { sesion.token = sessionStorage.getItem(LLAVE_TOKEN) || ''; } catch (e) { sesion.token = ''; }

export function guardarToken(token) {
  sesion.token = token || '';
  try {
    if (token) sessionStorage.setItem(LLAVE_TOKEN, token);
    else sessionStorage.removeItem(LLAVE_TOKEN);
  } catch (e) {}
}

const LLAVE_EQUIPO = 'llave-equipo';

export function leerLlave() {
  try { return localStorage.getItem(LLAVE_EQUIPO) || ''; } catch (e) { return ''; }
}

export function guardarLlave(llave) {
  try {
    if (llave) localStorage.setItem(LLAVE_EQUIPO, llave);
    else localStorage.removeItem(LLAVE_EQUIPO);
  } catch (e) {}
}

/* fetch con tiempo maximo: sin WiFi un fetch puede quedarse colgado minutos */
export function pedir(ruta, opciones, ms) {
  const corte = new AbortController();
  const plazo = setTimeout(() => corte.abort(), ms);
  opciones.signal = corte.signal;
  return fetch(API_BASE + ruta, opciones)
    .then((r) => r.json())
    .finally(() => clearTimeout(plazo));
}

export function llamar(ruta, datos, ms) {
  return pedir(ruta, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Sesion': sesion.token },
    body: JSON.stringify(datos || {})
  }, ms || 5000);
}

export function descargar(ruta, datos, ms) {
  const corte = new AbortController();
  const plazo = setTimeout(() => corte.abort(), ms || 20000);
  return fetch(API_BASE + ruta, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Sesion': sesion.token },
    body: JSON.stringify(datos || {}),
    signal: corte.signal
  }).then((r) => {
    if ((r.headers.get('Content-Type') || '').startsWith('application/json')) return r.json();
    if (!r.ok) return null;
    const nombre = /filename="([^"]+)"/.exec(r.headers.get('Content-Disposition') || '');
    return r.blob().then((archivo) => ({ ok: true, archivo, nombre: nombre ? nombre[1] : 'descarga' }));
  }).finally(() => clearTimeout(plazo));
}

/* Igual que llamar, pero deja constancia en el registro de comandos */
export function enviar(ruta, datos) {
  registrar('→ ' + ruta + (datos ? ' ' + JSON.stringify(datos) : ''));
  return llamar(ruta, datos).then((r) => {
    if (r && r.mensaje) registrar('← ' + r.mensaje);
    return r;
  }, () => {
    registrar('← sin respuesta');   // si la red se cayo, la consulta de estado lo detecta
    return null;
  });
}
