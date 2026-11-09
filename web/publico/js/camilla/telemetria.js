/* Lecturas que llegan de la camilla y su API publica en window.camilla. */
import { CONFIG } from '../config.js';
import { panel } from '../estado.js';
import { pintar } from '../ui/pintado.js';
import { activarParo, detenerManual, irA } from './movimiento.js';

/* Angulos desde los sensores: {cabeza: 32, piernas: 14} */
export function aplicarAngulos(lectura) {
  ['cabeza', 'piernas'].forEach((s) => {
    if (typeof lectura[s] === 'number' && !CONFIG[s].continua) {   // sin sensor, el servidor no conoce su posicion
      panel.valor[s] = Math.round(Math.min(CONFIG[s].max, Math.max(CONFIG[s].min, lectura[s])));
    }
  });
  pintar();
}

/* Finales de carrera de la altura: 'superior' | 'inferior' | null */
function topeAltura(cual) {
  if (cual === 'superior') panel.valor.altura = CONFIG.altura.max;
  else if (cual === 'inferior') panel.valor.altura = CONFIG.altura.min;
  detenerManual();
  pintar();
}

function estadoPublico() {
  const { valor, paro, bloqueo } = panel;
  return { cabeza: valor.cabeza, piernas: valor.piernas, paro, bloqueo };
}

export function exponerApi() {
  window.camilla = { aplicarAngulos, topeAltura, estado: estadoPublico, irA, paro: activarParo };
}
