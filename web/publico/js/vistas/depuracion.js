/* Depuracion: solo el perfil Desarrollador (el servidor tambien lo revisa).
   Mientras el panel esta abierto pregunta POST /api/depuracion cada segundo:
   ESP32 (puerto, ultima orden y respuesta), sensores, motor, sesiones y el
   registro del servidor, sin tener que entrar por SSH a ver journalctl. */
import { llamar } from '../api/cliente.js';
import { sesion } from '../estado.js';
import { porId } from '../utilidades.js';

const CADA_MS = 1000;
const detalles = porId('detallesDepuracion');
const estado = porId('depEstado');
const registro = porId('depRegistro');
let reloj = null;

function linea(nombre, valor) {
  return (nombre + '            ').slice(0, 12) + valor;
}

function textoAltura(a) {
  if (!a) return 'sin datos de pasos';
  const tope = (v) => (v === null ? '—' : String(v));
  return `${a.modo} · ${a.pasos} pasos · ${a.centro ? 'con' : 'sin'} centro · topes ${tope(a.topes.abajo)} / ${tope(a.topes.arriba)}`;
}

function textoSensores(sensores) {
  const partes = ['cabeza', 'piernas'].map((s) => {
    const v = sensores[s];
    if (!v) return s + ': sin sensor';
    return s + ': ' + v.estado + (v.angulo === null ? '' : ' ' + v.angulo + '°');
  });
  return partes.join(' · ');
}

function pintar(d) {
  const e = d.esp32 || {};
  const motor = d.motor ? `${d.motor.seccion} ${d.motor.dir > 0 ? '↑' : '↓'} (orden hace ${d.motor.hace_ms} ms)` : 'quieto';
  /* textContent: aqui hay nombres de usuario y lineas del registro */
  estado.textContent = [
    linea('Modo', d.simulacion ? 'simulador (no mueve motores)' : 'ESP32 real'),
    linea('ESP32', e.puerto ? `${e.puerto} · respondió hace ${e.hace_ms} ms` : 'sin conexión'),
    linea('Envía', e.ultima_orden || '—'),
    linea('Recibe', e.ultima_respuesta || '—'),
    linea('Sensores', textoSensores(d.sensores || {})),
    linea('Altura', textoAltura(d.altura)),
    linea('Motor', motor),
    linea('Paro', d.paro ? 'ACTIVO' : 'no'),
    linea('Control', d.titular || 'nadie'),
    linea('Sesiones', ''),
    ...(d.sesiones || []).map((s) => `  ${s.usuario} (${s.rol}) ${s.ip || '-'} · hace ${s.hace_s} s`)
  ].join('\n');
  const abajo = registro.scrollTop + registro.clientHeight >= registro.scrollHeight - 8;
  registro.textContent = (d.registro || []).join('\n') || 'Sin mensajes del servidor.';
  if (abajo) registro.scrollTop = registro.scrollHeight;   // si estaba leyendo arriba, no lo mueve
}

function consultar() {
  if (!detalles.open || sesion.rol !== 'dev') {
    detener();
    return;
  }
  llamar('/api/depuracion', {}, 2500).then((d) => {
    if (d && d.ok) pintar(d);
    else estado.textContent = (d && d.mensaje) || 'Sin respuesta.';
  }, () => { estado.textContent = 'Sin respuesta del servidor.'; });
}

function detener() {
  clearInterval(reloj);
  reloj = null;
}

export function iniciarDepuracion() {
  detalles.addEventListener('toggle', () => {
    detener();
    if (detalles.open) {
      consultar();
      reloj = setInterval(consultar, CADA_MS);
    }
  });
}
