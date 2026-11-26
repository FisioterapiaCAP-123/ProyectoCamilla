/* Altura: automatico o manual (pedal) y los pasos del motor (centro y topes).
   Solo el perfil Desarrollador; el servidor tambien lo revisa. El panel de pasos va dentro
   de la tarjeta, porque entre un tope y otro hay que mover la altura con sus botones.
   Lo que se ve lo pinta ui/pintado.js segun panel.altura. */
import { SERVIDOR } from '../api/ordenes.js';
import { panel } from '../estado.js';
import { pintar } from '../ui/pintado.js';
import { porId } from '../utilidades.js';

const CONFIRMAR_MS = 4000;   // "Borrar topes" se toca dos veces dentro de este tiempo
let borrarPedido = 0;

function mensaje(id, texto) {
  porId(id).textContent = texto || '';
}

function mandar(accion, id) {
  mensaje(id, '');
  SERVIDOR.altura(accion).then((r) => {
    if (!r) mensaje(id, 'No hubo respuesta del servidor. Intenta de nuevo.');
    else if (!r.ok) mensaje(id, r.mensaje || 'No se pudo.');
    pintar();
  });
}

export function iniciarAltura() {
  document.addEventListener('click', (e) => {
    if (e.target.closest('[data-abrir-pasos]')) {
      panel.pasosAbiertos = true;
      mensaje('pasosMensaje', '');
      pintar();
      return;
    }
    if (e.target.closest('[data-cerrar-pasos]')) {
      panel.pasosAbiertos = false;
      pintar();
      return;
    }
    const boton = e.target.closest('[data-altura]');
    if (!boton || boton.disabled) return;
    const accion = boton.dataset.altura;
    if (accion === 'borrar' && Date.now() - borrarPedido > CONFIRMAR_MS) {
      borrarPedido = Date.now();
      mensaje('pasosMensaje', 'Toca Borrar topes otra vez para confirmar: la altura queda sin topes.');
      return;
    }
    borrarPedido = 0;
    boton.disabled = true;   // hasta la proxima consulta: un toque, una orden
    mandar(accion, 'pasosMensaje');
  });
  document.querySelectorAll('input[name="modoAltura"]').forEach((radio) => {
    radio.addEventListener('change', () => {
      if (radio.checked) mandar(radio.value, 'modoMensajeAltura');
    });
  });
}
