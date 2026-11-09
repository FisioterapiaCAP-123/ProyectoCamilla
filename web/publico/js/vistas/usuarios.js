/* Pestana Usuarios: perfiles y sus roles (solo administrador). */
import { ADMIN } from '../api/admin.js';
import { ROLES } from '../config.js';
import { sesion } from '../estado.js';
import { mostrarAviso, revisar } from '../ui/avisos.js';
import { marcarCampo, revisarClave } from '../ui/formularios.js';
import { abrirModal, cerrarModal, confirmar } from '../ui/modales.js';
import { esc, porId } from '../utilidades.js';

const tabla = porId('listaUsuarios');
const campoClave = porId('claveNueva');

let usuarios = [];
let perfilClave = null;   // a quien se le cambia la contrasena

export function cargarUsuarios() {
  ADMIN.usuarios().then((r) => {
    if (!revisar(r)) return;
    usuarios = r.usuarios;
    pintarUsuarios();
  }, () => revisar(null));
}

function opcion(accion, id, texto, clase = '') {
  return `<li><button type="button" class="dropdown-item py-2 ${clase}" data-accion="${accion}" data-id="${id}">${texto}</button></li>`;
}

function menuAcciones(u) {
  return '<div class="dropdown">' +
    '<button type="button" class="btn btn-outline-secondary btn-sm dropdown-toggle" data-bs-toggle="dropdown" ' +
            'data-bs-popper-config=\'{"strategy":"fixed"}\' aria-expanded="false">Opciones</button>' +
    '<ul class="dropdown-menu dropdown-menu-end shadow">' +
      opcion('rol', u.id, u.rol === 'admin' ? 'Hacer fisioterapeuta' : 'Hacer administrador') +
      opcion('activo', u.id, u.activo ? 'Desactivar' : 'Activar') +
      opcion('clave', u.id, 'Cambiar contraseña') +
      '<li><hr class="dropdown-divider"></li>' +
      opcion('borrar', u.id, 'Borrar perfil', 'text-danger') +
    '</ul></div>';
}

function filaUsuario(u) {
  const yo = u.usuario === sesion.usuario;
  let rol = `<span class="badge rounded-pill ${u.rol === 'admin' ? 'text-bg-primary' : 'text-bg-light border'}">${esc(ROLES[u.rol] || u.rol)}</span>`;
  if (!u.activo) rol += ' <span class="badge rounded-pill text-bg-danger">Desactivado</span>';
  const acciones = yo ? '<span class="badge rounded-pill text-bg-success">Tú</span>' : menuAcciones(u);
  return `<tr${u.activo ? '' : ' class="opacity-75"'}>` +
    `<td class="ps-3"><div class="fw-semibold text-break">${esc(u.nombre)}</div>` +
      `<div class="tipo-dato small text-break text-body-secondary">@${esc(u.usuario)}</div></td>` +
    `<td>${rol}</td>` +
    `<td class="d-none d-md-table-cell tipo-dato small text-nowrap text-body-secondary">${esc(u.creado)}</td>` +
    `<td class="text-end pe-3">${acciones}</td></tr>`;
}

function pintarUsuarios() {
  tabla.innerHTML = usuarios.map(filaUsuario).join('');
  porId('cuentaUsuarios').textContent = usuarios.length;
}

function cambiarUsuario(accion, datos, aviso) {
  ADMIN.cambiarUsuario(accion, datos).then((r) => {
    if (!revisar(r)) return;
    mostrarAviso(aviso, 'ok');
    cargarUsuarios();
  }, () => revisar(null));
}

function hacerAdministrador(u) {
  confirmar(`¿Hacer administrador a ${u.nombre}?`,
    'Podrá ver los registros de pacientes y manejar los perfiles.', 'Hacer administrador', false,
    () => cambiarUsuario('rol', { id: u.id, rol: 'admin' }, `${u.nombre} ahora es administrador`));
}

function quitarAdministrador(u) {
  confirmar(`¿Quitarle el rol de administrador a ${u.nombre}?`,
    'Queda como fisioterapeuta: ya no verá los registros ni los perfiles.', 'Quitar rol', true,
    () => cambiarUsuario('rol', { id: u.id, rol: 'fisio' }, `${u.nombre} ahora es fisioterapeuta`));
}

function desactivar(u) {
  confirmar(`¿Desactivar a ${u.nombre}?`,
    'No podrá entrar hasta que lo actives otra vez. Si está conectado, su sesión se cierra.', 'Desactivar', true,
    () => cambiarUsuario('activo', { id: u.id, activo: false }, `${u.nombre} quedó desactivado`));
}

function borrar(u) {
  confirmar(`¿Borrar el perfil de ${u.nombre}?`,
    'Se borra para siempre. Si está conectado, su sesión se cierra. Los registros que agregó se quedan.', 'Borrar', true,
    () => cambiarUsuario('borrar', { id: u.id }, `Perfil de ${u.nombre} borrado`));
}

function pedirClaveNueva(u) {
  perfilClave = u;
  porId('claveNombre').textContent = u.nombre;
  campoClave.value = '';
  campoClave.classList.remove('is-invalid');
  abrirModal('modalClave');
}

const ACCIONES = {
  rol: (u) => (u.rol === 'admin' ? quitarAdministrador(u) : hacerAdministrador(u)),
  activo: (u) => (u.activo ? desactivar(u) : cambiarUsuario('activo', { id: u.id, activo: true }, `${u.nombre} puede entrar otra vez`)),
  borrar,
  clave: pedirClaveNueva
};

function guardarClaveNueva(e) {
  e.preventDefault();
  campoClave.classList.remove('is-invalid');
  const error = revisarClave(campoClave.value);
  if (error) return marcarCampo(campoClave, error);
  const u = perfilClave;
  cerrarModal();
  cambiarUsuario('clave', { id: u.id, clave: campoClave.value }, `Contraseña de ${u.nombre} cambiada`);
  campoClave.value = '';
}

export function olvidarUsuarios() {
  usuarios = [];
  tabla.innerHTML = '';
}

export function iniciarUsuarios() {
  tabla.addEventListener('click', (e) => {
    const boton = e.target.closest('[data-accion]');
    if (!boton) return;
    const id = parseInt(boton.dataset.id, 10);
    const usuario = usuarios.find((u) => u.id === id);
    if (usuario) ACCIONES[boton.dataset.accion](usuario);
  });
  porId('modalClave').addEventListener('shown.bs.modal', () => campoClave.focus());
  porId('btnClaveNo').addEventListener('click', cerrarModal);
  porId('formClave').addEventListener('submit', guardarClaveNueva);
}
