/* Movimiento de la camilla: botones sostenidos, "Ir a" y paro. */
import { SERVIDOR } from '../api/ordenes.js';
import { CONFIG, RITMO, SECCIONES, SUFIJO } from '../config.js';
import { panel, puedeMover } from '../estado.js';
import { anunciar, pintar } from '../ui/pintado.js';
import { registrar } from '../ui/registro.js';
import { porId, signo } from '../utilidades.js';

const DURACION_TOPE_MS = 1800;
const topeId = { cabeza: null, piernas: null };

function darPaso(seccion, dir) {
  const c = CONFIG[seccion];
  const siguiente = Math.max(c.min, Math.min(c.max, panel.valor[seccion] + dir * c.paso));
  if (siguiente === panel.valor[seccion]) {
    marcarTope(seccion);
    return false;
  }
  panel.valor[seccion] = siguiente;
  if (!c.continua) SERVIDOR.paso(seccion, dir);   // con motor continuo no hay comando por paso
  pintar();
  return true;
}

function marcarTope(seccion) {
  const c = CONFIG[seccion];
  registrar('FINAL DE CARRERA ' + seccion.toUpperCase() +
            (panel.valor[seccion] >= c.max ? ' SUPERIOR' : ' INFERIOR'));
  if (c.numerica) {
    const aviso = porId('tope' + SUFIJO[seccion]);
    aviso.classList.remove('d-none');
    clearTimeout(topeId[seccion]);
    topeId[seccion] = setTimeout(() => aviso.classList.add('d-none'), DURACION_TOPE_MS);
  }
  detenerManual();
  pintar();
}

export function iniciarManual(seccion, dir) {
  if (!puedeMover()) return;
  if (panel.manual && panel.manual.seccion === seccion && panel.manual.dir === dir) return;
  detenerTodo();

  const c = CONFIG[seccion];
  panel.manual = { seccion, dir, esperaId: null, repeticionId: null };
  if (c.continua) SERVIDOR.mover(seccion, dir);   // el motor arranca y queda corriendo
  pintar();

  if (!darPaso(seccion, dir)) return;

  const intervalo = c.continua ? RITMO.repeticionAltura : RITMO.repeticion;
  const espera    = c.continua ? 0 : RITMO.esperaRepeticion;

  panel.manual.esperaId = setTimeout(() => {
    if (!panel.manual) return;
    panel.manual.repeticionId = setInterval(() => {
      if (!panel.manual || !puedeMover()) {
        detenerManual();
        return;
      }
      darPaso(panel.manual.seccion, panel.manual.dir);
    }, intervalo);
  }, espera);
}

export function detenerManual() {
  const { manual } = panel;
  if (!manual) return;
  clearTimeout(manual.esperaId);
  clearInterval(manual.repeticionId);
  panel.manual = null;
  SERVIDOR.detener(manual.seccion);
  anunciar();
  pintar();
}

export function irA(objetivos, nombre) {
  if (!puedeMover()) return;
  detenerTodo();

  const destino = { altura: null, cabeza: null, piernas: null, nombre, timerId: null };
  panel.destino = destino;
  SECCIONES.forEach((s) => {
    if (typeof objetivos[s] === 'number') {
      destino[s] = Math.round(Math.min(CONFIG[s].max, Math.max(CONFIG[s].min, objetivos[s])));
    }
  });
  registrar('DESTINO ' + nombre.toUpperCase() + '  ' +
    SECCIONES.filter((s) => destino[s] !== null).map((s) => s + '=' + destino[s]).join('  '));

  destino.timerId = setInterval(() => {
    if (!puedeMover()) {
      cancelarDestino();
      return;
    }
    let movio = false;
    SECCIONES.forEach((s) => {
      if (destino[s] === null || destino[s] === panel.valor[s]) return;
      if (darPaso(s, signo(destino[s] - panel.valor[s]))) movio = true;
    });
    if (!movio) {
      registrar('DESTINO ' + destino.nombre.toUpperCase() + ' ALCANZADO');
      cancelarDestino();
      anunciar();
    }
  }, RITMO.automatico);

  pintar();
}

function cancelarDestino() {
  if (!panel.destino) return;
  clearInterval(panel.destino.timerId);
  panel.destino = null;
  pintar();
}

/* Corta lo que este en marcha, sea un boton sostenido o un "Ir a" */
export function detenerTodo() {
  detenerManual();
  cancelarDestino();
}

/* remoto = el aviso vino del servidor (otro dispositivo): no hay que reenviarlo */
export function activarParo(remoto) {
  panel.paro = true;
  detenerTodo();
  if (!remoto) SERVIDOR.paro(true);
  pintar();
}

export function liberarParo(remoto) {
  panel.paro = false;
  if (!remoto) SERVIDOR.paro(false);
  pintar();
}

export function alternarParo() {
  if (panel.paro) liberarParo();
  else activarParo();
}
