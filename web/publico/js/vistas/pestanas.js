/* Pestanas del panel y lo que cada rol puede ver.
   Para agregar una: su parcial e incluir en plantillas/panel/, su boton en
   pestanas.html y una entrada en PESTANAS. */
import { ROLES } from '../config.js';
import { detenerTodo } from '../camilla/movimiento.js';
import { panel, sesion } from '../estado.js';
import { pintarParoFlotante } from '../ui/pintado.js';
import { porId } from '../utilidades.js';
import { cargarPacientes } from './pacientes.js';
import { cargarUsuarios } from './usuarios.js';

const PESTANAS = {
  control:   { nodo: porId('pestanaControl') },
  registros: { nodo: porId('pestanaRegistros'), alAbrir: cargarPacientes },
  usuarios:  { nodo: porId('pestanaUsuarios'),  alAbrir: cargarUsuarios }
};

const navegacion = porId('pestanas');

function mostrarPestana(cual) {
  if (cual !== 'control') detenerTodo();   // al salir de Control no queda nada moviendose
  panel.pestana = cual;
  Object.entries(PESTANAS).forEach(([nombre, { nodo }]) => { nodo.hidden = nombre !== cual; });
  navegacion.querySelectorAll('[data-pestana]').forEach((boton) => {
    const activa = boton.dataset.pestana === cual;
    boton.classList.toggle('active', activa);
    boton.setAttribute('aria-selected', activa ? 'true' : 'false');
  });
  porId('btnBloqueo').classList.toggle('d-none', cual !== 'control');
  if (PESTANAS[cual].alAbrir) PESTANAS[cual].alAbrir();
  pintarParoFlotante();
}

export function aplicarRol(rol) {
  sesion.rol = rol || null;
  porId('perfilRol').textContent = ROLES[rol] || '';
  navegacion.hidden = rol !== 'admin';
  if (rol !== 'admin' && panel.pestana !== 'control') mostrarPestana('control');
}

export function iniciarPestanas() {
  navegacion.addEventListener('click', (e) => {
    const boton = e.target.closest('[data-pestana]');
    if (boton && boton.dataset.pestana !== panel.pestana) mostrarPestana(boton.dataset.pestana);
  });
}
