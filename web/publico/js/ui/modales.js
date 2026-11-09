/* Modales de Bootstrap: solo uno abierto a la vez, y la cuenta regresiva. */
import { panel } from '../estado.js';
import { porId } from '../utilidades.js';
import { pintarParoFlotante } from './pintado.js';

const MODALES = {};
let cuentaId = null;
let alConfirmar = null;

export function abrirModal(id) {
  if (panel.modalActivo && panel.modalActivo !== id) MODALES[panel.modalActivo].hide();
  panel.modalActivo = id;
  MODALES[id].show();
  pintarParoFlotante();
}

export function cerrarModal() {
  if (!panel.modalActivo) return;
  MODALES[panel.modalActivo].hide();
  panel.modalActivo = null;
  detenerCuenta();
  pintarParoFlotante();
}

export function iniciarCuenta(total, nodoSegundos, nodoBarra, alTerminar) {
  detenerCuenta();
  let restan = total;
  function dibujar() {
    nodoSegundos.textContent = restan + ' s';
    nodoBarra.style.width = (restan / total * 100) + '%';
    nodoBarra.parentElement.setAttribute('aria-valuenow', restan);
  }
  dibujar();
  cuentaId = setInterval(() => {
    restan--;
    dibujar();
    if (restan <= 0) {
      detenerCuenta();
      alTerminar();
    }
  }, 1000);
}

export function detenerCuenta() {
  clearInterval(cuentaId);
  cuentaId = null;
}

/* Los textos van con textContent: pueden traer nombres de personas */
export function confirmar(titulo, texto, boton, peligro, accion) {
  porId('tConfirmar').textContent = titulo;
  porId('confirmarTexto').textContent = texto;
  const si = porId('btnConfirmarSi');
  si.textContent = boton;
  si.classList.toggle('btn-danger', peligro);
  si.classList.toggle('btn-primary', !peligro);
  const caja = porId('confirmarCaja');
  caja.classList.toggle('tope-peligro', peligro);
  caja.classList.toggle('tope-altura', !peligro);
  alConfirmar = accion;
  abrirModal('modalConfirmar');
}

/* backdrop estatico y sin ESC: una cesion de control es una decision,
   no se cierra por accidente. Cualquier .modal del HTML queda registrado. */
export function iniciarModales() {
  document.querySelectorAll('.modal').forEach((nodo) => {
    MODALES[nodo.id] = new bootstrap.Modal(nodo, { backdrop: 'static', keyboard: false });
    nodo.addEventListener('hidden.bs.modal', () => {
      if (panel.modalActivo === nodo.id) {
        panel.modalActivo = null;
        detenerCuenta();
      }
      pintarParoFlotante();
    });
  });

  porId('btnConfirmarSi').addEventListener('click', () => {
    const accion = alConfirmar;
    alConfirmar = null;
    cerrarModal();
    if (accion) accion();
  });
  porId('btnConfirmarNo').addEventListener('click', () => {
    alConfirmar = null;
    cerrarModal();
  });
}
