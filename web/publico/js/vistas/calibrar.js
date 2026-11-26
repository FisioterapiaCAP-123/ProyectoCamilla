/* Calibrar los sensores de angulo (MPU6050): solo el perfil Desarrollador.
   El panel va dentro de la tarjeta de la seccion (no en un modal), porque entre
   "Guardar plano" y "Guardar subido" hay que mover la seccion con sus botones.
   Lo que muestra el panel lo pinta ui/pintado.js segun panel.sensores. */
import { SERVIDOR } from '../api/ordenes.js';
import { panel } from '../estado.js';
import { pintar } from '../ui/pintado.js';
import { porId } from '../utilidades.js';
import { SUFIJO } from '../config.js';

function mensaje(seccion, texto) {
  porId('calMensaje' + SUFIJO[seccion]).textContent = texto || '';
}

export function iniciarCalibrar() {
  document.addEventListener('click', (e) => {
    const abrir = e.target.closest('[data-abrir-calibrar]');
    if (abrir) {
      panel.calibrando = abrir.dataset.abrirCalibrar;
      mensaje(panel.calibrando, '');
      pintar();
      return;
    }
    const cerrar = e.target.closest('[data-cerrar-calibrar]');
    if (cerrar) {
      panel.calibrando = null;
      pintar();
      return;
    }
    const boton = e.target.closest('[data-calibrar]');
    if (!boton || boton.disabled) return;
    const seccion = boton.dataset.calibrar;
    mensaje(seccion, '');
    boton.disabled = true;   // hasta la proxima consulta: un toque, una orden
    SERVIDOR.calibrar(seccion, boton.dataset.posicion).then((r) => {
      if (!r) mensaje(seccion, 'No hubo respuesta del servidor. Intenta de nuevo.');
      else if (!r.ok) mensaje(seccion, r.mensaje || 'No se pudo guardar.');
      pintar();
    });
  });
}
