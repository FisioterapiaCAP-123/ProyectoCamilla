/* Lecturas que llegan de la camilla y su API publica en window.camilla. */
import { CONFIG } from '../config.js';
import { panel } from '../estado.js';
import { pintar } from '../ui/pintado.js';
import { activarParo, irA } from './movimiento.js';

/* Angulos desde los sensores: {cabeza: 32, piernas: 14} */
export function aplicarAngulos(lectura) {
  ['cabeza', 'piernas'].forEach((s) => {
    if (typeof lectura[s] === 'number' && !CONFIG[s].continua) {   // sin sensor, el servidor no conoce su posicion
      panel.valor[s] = Math.round(Math.min(CONFIG[s].max, Math.max(CONFIG[s].min, lectura[s])));
    }
  });
  pintar();
}

function estadoPublico() {
  const { valor, paro, bloqueo } = panel;
  return { cabeza: valor.cabeza, piernas: valor.piernas, paro, bloqueo };
}

export function exponerApi() {
  window.camilla = { aplicarAngulos, estado: estadoPublico, irA, paro: activarParo };
}
