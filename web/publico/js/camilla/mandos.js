/* Eventos de los mandos: botones de hombre muerto y barra inferior. */
import { panel } from '../estado.js';
import { pintar } from '../ui/pintado.js';
import { registrar } from '../ui/registro.js';
import { porId } from '../utilidades.js';
import { activarParo, alternarParo, detenerManual, detenerTodo, iniciarManual } from './movimiento.js';

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

function alternarBloqueo() {
  panel.bloqueo = !panel.bloqueo;
  if (panel.bloqueo) detenerTodo();
  registrar(panel.bloqueo ? 'CONTROLES BLOQUEADOS' : 'CONTROLES DESBLOQUEADOS');
  pintar();
}

export function iniciarMandos() {
  document.querySelectorAll('.btn-mover').forEach(conectarBotonMover);

  /* Hombre muerto: soltar en cualquier parte, o perder la pagina, detiene el movimiento */
  window.addEventListener('pointerup', detenerManual);
  window.addEventListener('pointercancel', detenerManual);
  window.addEventListener('blur', detenerManual);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) detenerManual();
  });

  porId('btnParo').addEventListener('click', alternarParo);
  porId('btnParoFlotante').addEventListener('click', alternarParo);
  porId('btnBloqueo').addEventListener('click', alternarBloqueo);

  document.addEventListener('keydown', (e) => {
    // En los formularios del administrador ESC solo cierra o borra; ahi no se esta moviendo nada
    if (e.target.closest && e.target.closest('.pestana-admin, #panelPaciente, #modalFicha, #modalClave, #modalConfirmar')) return;
    if (e.key === 'Escape' && !panel.paro) activarParo();
  });
}
