/* Dibujo SVG de la camilla: inclinacion, arcos de angulo y elevador. */
import { CONFIG } from '../config.js';
import { estaMoviendo, panel } from '../estado.js';
import { conSigno, porId } from '../utilidades.js';

const PIVOTE = { cabeza: { x: 248, y: 240 }, piernas: { x: 392, y: 240 } };
const R_ARCO = 68;
const R_ETIQUETA = 93;
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
  segmento:     { cabeza: porId('segCabeza'),     piernas: porId('segPiernas') },
  arco:         { cabeza: porId('arcoCabeza'),    piernas: porId('arcoPiernas') },
  etiqueta:     { cabeza: porId('etqArcoCabeza'), piernas: porId('etqArcoPiernas') }
};

function polar(cx, cy, r, grados) {
  const a = grados * Math.PI / 180;
  return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
}

function trazarArco(cx, cy, r, a0, a1) {
  const p0 = polar(cx, cy, r, a0);
  const p1 = polar(cx, cy, r, a1);
  return `M ${p0[0].toFixed(2)} ${p0[1].toFixed(2)} A ${r} ${r} 0 0 ${a1 > a0 ? 1 : 0} ${p1[0].toFixed(2)} ${p1[1].toFixed(2)}`;
}

function pintarArco(seccion, grados, aBase, sentido) {
  const p = PIVOTE[seccion];
  const arco = el.arco[seccion];
  const etiqueta = el.etiqueta[seccion];
  if (grados === 0) {
    arco.setAttribute('d', '');
    etiqueta.textContent = '';
    return;
  }
  arco.setAttribute('d', trazarArco(p.x, p.y, R_ARCO, aBase, aBase + sentido * grados));
  const medio = polar(p.x, p.y, R_ETIQUETA, aBase + sentido * grados / 2);
  etiqueta.setAttribute('x', medio[0].toFixed(1));
  etiqueta.setAttribute('y', medio[1].toFixed(1));
  etiqueta.textContent = conSigno(grados) + '°';
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
  const { valor } = panel;
  el.segmento.cabeza.setAttribute('transform',  `rotate(${valor.cabeza} ${PIVOTE.cabeza.x} ${PIVOTE.cabeza.y})`);
  el.segmento.piernas.setAttribute('transform', `rotate(${-valor.piernas} ${PIVOTE.piernas.x} ${PIVOTE.piernas.y})`);
  el.segmento.cabeza.classList.toggle('activo',  estaMoviendo('cabeza'));
  el.segmento.piernas.classList.toggle('activo', estaMoviendo('piernas'));

  pintarArco('cabeza',  valor.cabeza,  180,  1);
  pintarArco('piernas', valor.piernas,   0, -1);
  pintarElevador();
}
