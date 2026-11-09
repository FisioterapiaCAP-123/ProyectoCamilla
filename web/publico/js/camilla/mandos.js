/* Eventos de los mandos: botones de hombre muerto, "Ir a" y barra inferior. */
import { CONFIG, SECCIONES_NUMERICAS, SUFIJO } from '../config.js';
import { panel } from '../estado.js';
import { pintar } from '../ui/pintado.js';
import { registrar } from '../ui/registro.js';
import { porId } from '../utilidades.js';
import { activarParo, alternarParo, detenerManual, detenerTodo, iniciarManual, irA } from './movimiento.js';

const TECLAS_PULSAR = [' ', 'Enter', 'Spacebar'];

function conectarBotonMover(boton) {
  const seccion = boton.dataset.seccion;
  const dir = parseInt(boton.dataset.dir, 10);
  boton.addEventListener('pointerdown', (e) => {
    e.preventDefault();
    iniciarManual(seccion, dir);
  });
  boton.addEventListener('pointerup', detenerManual);
  boton.addEventListener('pointerleave', detenerManual);
  boton.addEventListener('pointercancel', detenerManual);
  boton.addEventListener('contextmenu', (e) => e.preventDefault());
  boton.addEventListener('keydown', (e) => {
    if (e.repeat || !TECLAS_PULSAR.includes(e.key)) return;
    e.preventDefault();
    iniciarManual(seccion, dir);
  });
  boton.addEventListener('keyup', (e) => {
    if (!TECLAS_PULSAR.includes(e.key)) return;
    e.preventDefault();
    detenerManual();
  });
  boton.addEventListener('blur', detenerManual);
}

/* Entrada directa de angulo (solo secciones con sensor) */
function conectarCampoAngulo(seccion) {
  const c = CONFIG[seccion];
  const suf = SUFIJO[seccion];
  const campo = porId('campo' + suf);
  const aviso = porId('aviso' + suf);

  campo.min = c.min;
  campo.max = c.max;
  campo.value = panel.valor[seccion];
  campo.setAttribute('aria-label', `${c.etiqueta} en grados, entre ${c.min} y ${c.max}`);

  function invalido(texto) {
    aviso.textContent = texto;
    campo.classList.add('is-invalid');
    campo.focus();
  }

  function enviar() {
    campo.classList.remove('is-invalid');
    const crudo = campo.value.trim();
    if (crudo === '' || isNaN(Number(crudo))) {
      invalido(`Escribe un número entre ${c.min}° y ${c.max}°.`);
      return;
    }
    const grados = Math.round(Number(crudo));
    if (grados < c.min || grados > c.max) {
      invalido(`Fuera de recorrido. Permitido de ${c.min}° a ${c.max}°.`);
      campo.select();
      return;
    }
    campo.value = grados;
    irA({ [seccion]: grados }, `${c.etiqueta} ${grados}°`);
  }

  porId('ir' + suf).addEventListener('click', enviar);
  campo.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      enviar();
    }
  });
  campo.addEventListener('input', () => campo.classList.remove('is-invalid'));
}

function alternarBloqueo() {
  panel.bloqueo = !panel.bloqueo;
  if (panel.bloqueo) detenerTodo();
  registrar(panel.bloqueo ? 'CONTROLES BLOQUEADOS' : 'CONTROLES DESBLOQUEADOS');
  pintar();
}

export function iniciarMandos() {
  document.querySelectorAll('.btn-mover').forEach(conectarBotonMover);
  SECCIONES_NUMERICAS.forEach(conectarCampoAngulo);

  /* Hombre muerto: soltar en cualquier parte, o perder la pagina, detiene el movimiento */
  window.addEventListener('pointerup', detenerManual);
  window.addEventListener('pointercancel', detenerManual);
  window.addEventListener('blur', detenerManual);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) detenerManual();
  });

  porId('btnParo').addEventListener('click', alternarParo);
  porId('btnParoFlotante').addEventListener('click', alternarParo);
  /* "Plano" solo endereza la camilla; la altura es ajuste del fisioterapeuta. */
  porId('btnPlano').addEventListener('click', () => irA({ cabeza: 0, piernas: 0 }, 'Plano'));
  porId('btnBloqueo').addEventListener('click', alternarBloqueo);

  document.addEventListener('keydown', (e) => {
    // En los formularios del administrador ESC solo cierra o borra; ahi no se esta moviendo nada
    if (e.target.closest && e.target.closest('.pestana-admin, #modalClave, #modalConfirmar')) return;
    if (e.key === 'Escape' && !panel.paro) activarParo();
  });
}
