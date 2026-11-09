/* Desplegable "Registro de comandos (desarrollo)" de la pestana Control. */
import { porId } from '../utilidades.js';

const MAXIMO_LINEAS = 80;
const LINEAS_VISIBLES = 12;

const salida = porId('logSalida');
const lineas = [];

function hora() {
  return new Date().toTimeString().slice(0, 8);
}

export function registrar(texto) {
  lineas.push(hora() + '  ' + texto);
  if (lineas.length > MAXIMO_LINEAS) lineas.shift();
  salida.textContent = lineas.slice(-LINEAS_VISIBLES).join('\n');
  salida.scrollTop = salida.scrollHeight;
}

/* Cualquier error de la pagina queda en el registro */
export function iniciarDiagnostico() {
  window.addEventListener('error', (ev) => registrar('ERROR: ' + ev.message));
  window.addEventListener('unhandledrejection', (ev) => {
    registrar('ERROR: ' + ((ev.reason && ev.reason.message) || ev.reason));
  });
}
