/* Estado compartido del panel. Los demas modulos lo leen y lo cambian desde aqui. */

export const panel = {
  /* La altura parte de media carrera: es solo el punto de partida del dibujo.
     Los angulos reales llegan con la primera consulta al servidor. */
  valor: { altura: 50, cabeza: 0, piernas: 0 },
  manual: null,       // { seccion, dir, esperaId, repeticionId }
  destino: null,      // { altura, cabeza, piernas, nombre, timerId }
  paro: false,
  bloqueo: false,
  pestana: 'control',
  modalActivo: null,
  ultimaOrden: 0,     // la posicion que llega del servidor se ignora un momento tras mover
  paroPedidoEn: 0     // y el paro, un momento tras pulsarlo, para que no parpadee
};

/* Quien esta operando la camilla ahora mismo. Lo dicta el servidor. */
export const control = { titular: null, usuario: null, soyYo: false, conectado: true };   // titular: nombre que se muestra

export const sesion = { usuario: null, nombre: null, rol: null, token: '' };

/* Mover exige tener el control. El PARO no: ese nunca depende de esto. */
export function puedeMover() {
  return !panel.paro && !panel.bloqueo && control.soyYo && control.conectado;
}

export function estaMoviendo(seccion) {
  const { manual, destino, valor } = panel;
  return Boolean((manual && manual.seccion === seccion) ||
                 (destino && destino[seccion] !== null && destino[seccion] !== valor[seccion]));
}
