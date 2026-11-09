/* Toasts de Bootstrap. */
import { porId } from '../utilidades.js';

const DURACION_MS = 5000;
const ESTILOS = {
  ok:    { borde: 'border-success',   texto: 'aviso-ok' },
  error: { borde: 'border-danger',    texto: 'aviso-error' },
  info:  { borde: 'border-secondary', texto: 'aviso-info' }
};

const zona = porId('zonaToasts');

export function mostrarAviso(texto, tipo) {
  const estilo = ESTILOS[tipo] || ESTILOS.info;
  const nodo = document.createElement('div');
  nodo.className = `toast align-items-center border border-2 ${estilo.borde}`;
  nodo.setAttribute('role', 'alert');
  nodo.innerHTML = '<div class="d-flex">' +
    `<div class="toast-body fw-semibold ${estilo.texto}"></div>` +
    '<button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast" aria-label="Cerrar"></button>' +
    '</div>';
  nodo.querySelector('.toast-body').textContent = texto;
  zona.appendChild(nodo);
  const toast = new bootstrap.Toast(nodo, { delay: DURACION_MS });
  nodo.addEventListener('hidden.bs.toast', () => nodo.remove());
  toast.show();
}

export function borrarAvisos() {
  zona.innerHTML = '';
}

/* Respuesta de un pedido de administracion: true si salio bien */
export function revisar(respuesta) {
  if (respuesta && respuesta.ok) return true;
  mostrarAviso((respuesta && respuesta.mensaje) || 'No se pudo contactar con la camilla. Revisa la conexión.', 'error');
  return false;
}
