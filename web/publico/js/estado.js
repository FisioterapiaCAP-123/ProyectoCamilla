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
  hardware: { conectado: true, secciones: ['altura', 'cabeza', 'piernas'] },   // lo actualiza el servidor
  /* Sensores de angulo (MPU6050) que informa el ESP32: {piernas: {angulo: 12.5|null,
     estado: 'ok'|'falla'|'sincal'|'plano'|'poco'}}. Sin entrada = esa seccion no tiene sensor. */
  sensores: {},
  calibrando: null,  // seccion con el panel de calibrar abierto (solo perfil Desarrollador)
  /* Pasos del motor de la altura que informa el ESP32: {pasos: 120, centro: true,
     topes: {abajo: -4000|null, arriba: 3800|null}, modo: 'auto'|'manual'}, o null si no los informa */
  altura: null,
  pasosAbiertos: false,  // panel "Pasos" de la altura abierto (solo perfil Desarrollador)
  paroPedidoEn: 0     // lo que diga el servidor del paro se ignora un momento tras pulsarlo, para que no parpadee
};

/* Quien esta operando la camilla ahora mismo. Lo dicta el servidor. */
export const control = { titular: null, usuario: null, soyYo: false, conectado: true };   // titular: nombre que se muestra

/* registros: {pin, abierto, pide_clave} en un equipo recordado de un administrador (vistas/pin.js), si no null */
export const sesion = { usuario: null, nombre: null, rol: null, token: '', registros: null };

/* Mover exige tener el control. El PARO no: ese nunca depende de esto. */
export function puedeMover(seccion) {
  if (panel.paro || panel.bloqueo || !control.soyYo || !control.conectado || !panel.hardware.conectado) return false;
  if (seccion === 'altura' && bloqueoAltura()) return false;
  return seccion === undefined || panel.hardware.secciones.includes(seccion);
}

const hayTopes = (a) => a.topes.abajo !== null || a.topes.arriba !== null;

/* Por que no se puede mover la altura (lo mismo revisa el servidor), o '' si se puede */
export function bloqueoAltura() {
  const a = panel.altura;
  if (!a) return '';
  if (a.modo === 'manual') return 'manual';
  if (hayTopes(a) && !a.centro && sesion.rol !== 'dev') return 'sincentro';
  return '';
}

/* Con sensor calibrado el angulo es real: la pagina no lo estima. La altura es real
   con el centro puesto y los dos topes guardados (el servidor la manda de 0 a 100). */
export function conSensor(seccion) {
  if (seccion === 'altura') {
    const a = panel.altura;
    return Boolean(a && a.modo === 'auto' && a.centro && a.topes.abajo !== null && a.topes.arriba !== null);
  }
  const s = panel.sensores[seccion];
  return Boolean(s && s.estado === 'ok');
}

export function estaMoviendo(seccion) {
  const { manual, destino, valor } = panel;
  return Boolean((manual && manual.seccion === seccion) ||
                 (destino && destino[seccion] !== null && destino[seccion] !== valor[seccion]));
}
