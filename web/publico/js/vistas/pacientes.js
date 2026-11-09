/* Pestana Registros: pacientes (solo administrador). */
import { ADMIN } from '../api/admin.js';
import { mostrarAviso, revisar } from '../ui/avisos.js';
import { marcarCampo } from '../ui/formularios.js';
import { confirmar } from '../ui/modales.js';
import { esc, porId, sinTildes } from '../utilidades.js';

const EDAD_MAXIMA = 120;
const ICONO_EDITAR = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13 7 4 4"/></svg>';
const ICONO_BORRAR = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 7h16"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M6 7l1 13h10l1-13"/><path d="M9 7V4h6v3"/></svg>';

const formulario = porId('formPaciente');
const campoNombre = porId('pacNombre');
const campoEdad = porId('pacEdad');
const tabla = porId('listaPacientes');
const buscador = porId('buscarPaciente');
const botonGuardar = porId('btnGuardarPaciente');
const botonCancelar = porId('btnCancelarPaciente');

let pacientes = [];
let editando = null;   // id del registro que se esta editando (null = nuevo)

export function cargarPacientes() {
  ADMIN.pacientes().then((r) => {
    if (!revisar(r)) return;
    pacientes = r.pacientes;
    pintarPacientes();
  }, () => revisar(null));
}

function filaPaciente(p) {
  return '<tr>' +
    `<td class="ps-3 fw-semibold text-break">${esc(p.nombre)}</td>` +
    `<td class="tipo-dato text-nowrap">${esc(p.edad)}</td>` +
    `<td class="d-none d-sm-table-cell tipo-dato small text-nowrap text-body-secondary">${esc(p.creado)}</td>` +
    '<td class="text-end text-nowrap pe-3">' +
      `<button type="button" class="btn btn-outline-secondary btn-sm me-1" data-editar="${p.id}" aria-label="Editar">${ICONO_EDITAR}</button>` +
      `<button type="button" class="btn btn-outline-danger btn-sm" data-borrar="${p.id}" aria-label="Borrar">${ICONO_BORRAR}</button>` +
    '</td></tr>';
}

function pintarPacientes() {
  const filtro = sinTildes(buscador.value.trim());
  const filas = pacientes.filter((p) => sinTildes(p.nombre).includes(filtro));
  tabla.innerHTML = filas.map(filaPaciente).join('');
  porId('cuentaPacientes').textContent = pacientes.length;
  const vacio = porId('sinPacientes');
  vacio.textContent = pacientes.length ? 'Ningún paciente coincide con la búsqueda.' : 'Todavía no hay registros.';
  vacio.classList.toggle('d-none', filas.length > 0);
}

function editarPaciente(p) {
  editando = p ? p.id : null;
  campoNombre.value = p ? p.nombre : '';
  campoEdad.value = p ? p.edad : '';
  campoNombre.classList.remove('is-invalid');
  campoEdad.classList.remove('is-invalid');
  porId('tituloPaciente').textContent = p ? 'Editar registro' : 'Nuevo registro';
  botonGuardar.textContent = p ? 'Guardar cambios' : 'Guardar';
  botonCancelar.classList.toggle('d-none', !p);
  if (p) {
    porId('tarjetaPaciente').scrollIntoView({ behavior: 'smooth', block: 'start' });
    campoNombre.focus({ preventScroll: true });
  }
}

function borrarPaciente(p) {
  confirmar('¿Borrar este registro?', `Se borrará el registro de ${p.nombre}. No se puede deshacer.`, 'Borrar', true, () => {
    ADMIN.borrarPaciente(p.id).then((r) => {
      if (!revisar(r)) return;
      if (editando === p.id) editarPaciente(null);
      mostrarAviso('Registro borrado', 'ok');
      cargarPacientes();
    }, () => revisar(null));
  });
}

function guardarPaciente(e) {
  e.preventDefault();
  const nombre = campoNombre.value.trim().replace(/\s+/g, ' ');
  const edad = Number(campoEdad.value);
  campoNombre.classList.remove('is-invalid');
  campoEdad.classList.remove('is-invalid');
  if (nombre.length < 2) return marcarCampo(campoNombre, 'Escribe el nombre del paciente.');
  if (campoEdad.value === '' || !Number.isInteger(edad) || edad < 0 || edad > EDAD_MAXIMA) {
    return marcarCampo(campoEdad, 'La edad debe ser un número entre 0 y 120.');
  }
  botonGuardar.disabled = true;
  ADMIN.guardarPaciente({ id: editando, nombre, edad }).then((r) => {
    botonGuardar.disabled = false;
    if (r && !r.ok && r.campo === 'nombre') return marcarCampo(campoNombre, r.mensaje);
    if (r && !r.ok && r.campo === 'edad') return marcarCampo(campoEdad, r.mensaje);
    if (!revisar(r)) return;
    mostrarAviso(editando ? 'Cambios guardados' : 'Registro guardado', 'ok');
    editarPaciente(null);
    cargarPacientes();
    campoNombre.focus();
  }, () => {
    botonGuardar.disabled = false;
    revisar(null);
  });
}

/* Al salir no quedan datos de pacientes en la pagina */
export function olvidarPacientes() {
  pacientes = [];
  tabla.innerHTML = '';
  buscador.value = '';
  editarPaciente(null);
}

export function iniciarPacientes() {
  buscador.addEventListener('input', pintarPacientes);
  botonCancelar.addEventListener('click', () => editarPaciente(null));
  formulario.addEventListener('submit', guardarPaciente);
  tabla.addEventListener('click', (e) => {
    const boton = e.target.closest('[data-editar], [data-borrar]');
    if (!boton) return;
    const id = parseInt(boton.dataset.editar || boton.dataset.borrar, 10);
    const paciente = pacientes.find((p) => p.id === id);
    if (!paciente) return;
    if (boton.dataset.editar) editarPaciente(paciente);
    else borrarPaciente(paciente);
  });
}
