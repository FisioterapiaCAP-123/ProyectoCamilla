/* Dibujo SVG de la camilla.

   Cabeza y piernas no tienen sensor: el dibujo no muestra su posicion real.
   Mientras se mantiene un boton, la seccion se anima en bucle (como un GIF):
   al subir va de abajo hacia arriba y vuelve a empezar; al bajar, al reves.
   La primera pasada arranca desde donde esta el dibujo, sin saltos.
   Al soltar, termina en el extremo de lo ultimo que se hizo y ahi se queda:
   si subio, queda arriba; si bajo, queda recta.
   La altura sigue su estimacion de recorrido, como la barra de su tarjeta. */
import { CONFIG } from '../config.js';
import { estaMoviendo, panel } from '../estado.js';
import { porId } from '../utilidades.js';

const PIVOTE = { cabeza: { x: 248, y: 240 }, piernas: { x: 392, y: 240 } };
/* Grados que recorre el dibujo en cada bucle: [desde, hasta]. Solo es animacion.
   La cabeza al bajar pasa un poco de recta, porque ese respaldo puede ir mas abajo */
const RECORRIDO = {
  cabeza:  { subir: [0, 35],  bajar: [35, -12] },
  piernas: { subir: [0, 30],  bajar: [30, 0] }
};
const BUCLE_MS = 1700;      // una pasada completa del bucle
const PAUSA_FINAL = 0.18;   // parte del bucle que se queda quieta al final, antes de reiniciar
const FINAL_MS = 350;       // al soltar, tiempo para llegar a la posicion final
/* Donde queda cada seccion al soltar: arriba si subio, recta si bajo */
const FINAL = { subir: (seccion) => RECORRIDO[seccion].subir[1], bajar: () => 0 };

const AMPLITUD_PX = 32;     // cuanto sube/baja el conjunto en el dibujo, en px
const SUPERFICIE_Y = 229;   // borde superior del colchon a media altura
const GROSOR_COLCHON = 22;
const PISTON_BASE = 340;    // el piston siempre termina aqui, dentro del manguito
const PISTON_MINIMO = 8;

const el = {
  conjunto:     porId('conjunto'),
  piston:       porId('piston'),
  elevador:     porId('elevador'),
  flechaArriba: porId('flechaArriba'),
  flechaAbajo:  porId('flechaAbajo'),
  segmento:     { cabeza: porId('segCabeza'), piernas: porId('segPiernas') }
};

const pose = { cabeza: 0, piernas: 0 };   // grados que se dibujan ahora
let animacion = null;   // { seccion, dir, partida, inicio } mientras se mantiene un boton
let cierre = null;      // { seccion, desde, hacia, inicio } al soltar, camino a la posicion final
let cuadroId = null;

const suave = (t) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2);   // ease-in-out

function dibujarSegmentos() {
  el.segmento.cabeza.setAttribute('transform',  `rotate(${pose.cabeza.toFixed(2)} ${PIVOTE.cabeza.x} ${PIVOTE.cabeza.y})`);
  el.segmento.piernas.setAttribute('transform', `rotate(${(-pose.piernas).toFixed(2)} ${PIVOTE.piernas.x} ${PIVOTE.piernas.y})`);
}

function cuadro(ahora) {
  cuadroId = null;
  if (animacion) {
    const { seccion, dir, partida, inicio } = animacion;
    const [desde, hasta] = RECORRIDO[seccion][dir > 0 ? 'subir' : 'bajar'];
    const recorrido = BUCLE_MS * (1 - PAUSA_FINAL);
    const pausa = BUCLE_MS * PAUSA_FINAL;
    // La primera pasada sale de donde estaba el dibujo y dura lo que le falta del recorrido
    const primera = desde === hasta ? 0 : recorrido * Math.min(1, Math.abs(hasta - partida) / Math.abs(hasta - desde));
    const pasado = ahora - inicio;
    if (pasado < primera + pausa) {
      const t = primera ? Math.min(1, pasado / primera) : 1;
      pose[seccion] = partida + (hasta - partida) * suave(t);
    } else {
      const t = Math.min(1, ((pasado - primera - pausa) % BUCLE_MS) / recorrido);
      pose[seccion] = desde + (hasta - desde) * suave(t);
    }
  }
  if (cierre) {   // puede seguir mientras otra seccion se anima
    const t = Math.min(1, (ahora - cierre.inicio) / FINAL_MS);
    pose[cierre.seccion] = cierre.desde + (cierre.hacia - cierre.desde) * suave(t);
    if (t >= 1) cierre = null;
  }
  dibujarSegmentos();
  if (animacion || cierre) cuadroId = requestAnimationFrame(cuadro);
}

function seguirAnimando() {
  if (cuadroId === null) cuadroId = requestAnimationFrame(cuadro);
}

/* Arranca, cambia o termina el bucle segun el boton que se mantiene */
function actualizarAnimacion() {
  const { manual } = panel;
  const quiere = manual && RECORRIDO[manual.seccion] ? { seccion: manual.seccion, dir: manual.dir } : null;
  if (quiere && animacion && animacion.seccion === quiere.seccion && animacion.dir === quiere.dir) return;
  if (animacion) {
    // La seccion que se soltaba (o que se deja por otra) va a su posicion final
    const { seccion, dir } = animacion;
    const hacia = FINAL[dir > 0 ? 'subir' : 'bajar'](seccion);
    if (quiere && quiere.seccion !== seccion) pose[seccion] = hacia;   // cambio directo: sin animar las dos
    else cierre = { seccion, desde: pose[seccion], hacia, inicio: performance.now() };
    animacion = null;
  }
  if (quiere) {
    if (cierre && cierre.seccion === quiere.seccion) cierre = null;
    animacion = { ...quiere, partida: pose[quiere.seccion], inicio: performance.now() };
  }
  seguirAnimando();
}

function pintarElevador() {
  const c = CONFIG.altura;
  const moviendo = estaMoviendo('altura');
  const { manual, valor } = panel;
  const proporcion = (valor.altura - c.min) / (c.max - c.min);   // 0 abajo, 1 arriba
  const dy = -(proporcion - 0.5) * 2 * AMPLITUD_PX;

  el.conjunto.setAttribute('transform', `translate(0 ${dy.toFixed(2)})`);

  const bordeInferior = SUPERFICIE_Y + dy + GROSOR_COLCHON;
  el.piston.setAttribute('y', bordeInferior.toFixed(2));
  el.piston.setAttribute('height', Math.max(PISTON_MINIMO, PISTON_BASE - bordeInferior).toFixed(2));

  el.elevador.classList.toggle('activo', moviendo);
  el.flechaArriba.hidden = !(moviendo && manual && manual.dir > 0);
  el.flechaAbajo.hidden  = !(moviendo && manual && manual.dir < 0);
}

export function pintarDibujo() {
  el.segmento.cabeza.classList.toggle('activo',  estaMoviendo('cabeza'));
  el.segmento.piernas.classList.toggle('activo', estaMoviendo('piernas'));
  actualizarAnimacion();
  pintarElevador();
}
