/* Lecturas que llegan de la camilla y su API publica en window.camilla. */
import { panel } from '../estado.js';
import { pintar } from '../ui/pintado.js';
import { activarParo, irA } from './movimiento.js';

/* Angulos reales de los sensores: {cabeza: 32.4, piernas: 14.1}. Solo traen las secciones
   con sensor calibrado; las demas siguen con la estimacion de la pagina. Se muestra el valor
   real aunque salga del rango (por ejemplo -1 en piernas): el riel lo recorta al dibujar. */
export function aplicarAngulos(lectura) {
  let cambio = false;
  ['cabeza', 'piernas'].forEach((s) => {
    if (typeof lectura[s] !== 'number') return;
    const valor = Math.round(lectura[s]);
    if (valor !== panel.valor[s]) {
      panel.valor[s] = valor;
      cambio = true;
    }
  });
  if (cambio) pintar();
}

function estadoPublico() {
  const { valor, paro, bloqueo } = panel;
  return { cabeza: valor.cabeza, piernas: valor.piernas, paro, bloqueo };
}

export function exponerApi() {
  window.camilla = { aplicarAngulos, estado: estadoPublico, irA, paro: activarParo };
}
