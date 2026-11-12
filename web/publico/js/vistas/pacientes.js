/* Pestana Registros: pacientes (solo administrador). Todos los campos son opcionales. */
import { ADMIN } from '../api/admin.js';
import { mostrarAviso, revisar } from '../ui/avisos.js';
import { marcarCampo } from '../ui/formularios.js';
import { abrirModal, cerrarModal, confirmar } from '../ui/modales.js';
import { esc, porId, sinTildes } from '../utilidades.js';

/* Reglas iguales a web/basedatos.py, que es quien de verdad las aplica */
const EDAD_MAXIMA = 120;
const MEDIDAS = {   // minimo, maximo, decimales, aviso
  estatura: [0.3, 2.5, 2, 'La estatura va de 0.30 a 2.50 m.'],
  peso: [1, 900, 1, 'El peso va de 1 a 900 lb.'],
  dolor: [0, 10, 0, 'El dolor es un número entero de 0 a 10.']   // escala EVA: 0 = sin dolor
};
const PARRAFOS = ['diagnostico', 'notas'];   // conservan los saltos de linea
const TELEFONOS = ['telefono', 'emergencia_telefono'];
const CORREO = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const MINUTOS_CITA = 5;   // la hora de la cita se elige de 5 en 5 minutos
const SEXOS = { F: 'Femenino', M: 'Masculino' };

const ICONO_EDITAR = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13 7 4 4"/></svg>';
const ICONO_BORRAR = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 7h16"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M6 7l1 13h10l1-13"/><path d="M9 7V4h6v3"/></svg>';
const VACIO = '<span class="text-body-secondary">—</span>';
const ORDEN = new Intl.Collator('es', { sensitivity: 'base' });

const formulario = porId('formPaciente');
const tabla = porId('listaPacientes');
const buscador = porId('buscarPaciente');
const botonGuardar = porId('btnGuardarPaciente');
const cita = { fecha: porId('pacCitaFecha'), hora: porId('pacCitaHora'), minuto: porId('pacCitaMinuto'), periodo: porId('pacCitaPeriodo') };

/* Cada dato del paciente -> su campo (atributo data-campo), en el orden del formulario.
   La proxima cita va aparte: son cuatro controles que se juntan en un solo dato */
const campos = {};
formulario.querySelectorAll('[data-campo]').forEach((c) => { campos[c.dataset.campo] = c; });

let pacientes = [];
let editando = null;   // id del registro que se esta editando (null = nuevo)
let enFicha = null;    // paciente que muestra la ficha de solo lectura
let panelFormulario = null;   // bootstrap.Offcanvas del formulario
let original = '';           // lo que tenia el formulario al abrirse (para avisar si hay cambios sin guardar)
let cerrarSinPreguntar = false;

/* ---------- formatos ---------- */
const dos = (n) => String(n).padStart(2, '0');
const fechaLocal = (d) => `${d.getFullYear()}-${dos(d.getMonth() + 1)}-${dos(d.getDate())}`;
const sinSeparadores = (texto) => String(texto || '').replace(/[\s()-]/g, '');

/* Grupos de numeros separados por espacios. Solo numeros: lo demas se descarta */
const GRUPOS_DPI = [4, 5, 4];        // 2345 67890 0101
const GRUPOS_TELEFONO = [4, 4];      // 5555 1234
function agrupar(texto, grupos) {
  const d = String(texto).replace(/\D/g, '');
  const partes = [];
  let inicio = 0;
  for (const largo of grupos) { partes.push(d.slice(inicio, inicio + largo)); inicio += largo; }
  return partes.filter(Boolean).join(' ');   // tambien a medias, mientras se escribe: 234567 -> 2345 67
}
const formatoDpi = (dpi) => agrupar(dpi, GRUPOS_DPI);
const formatoTelefono = (tel) => agrupar(tel, GRUPOS_TELEFONO);

/* Mascara de numeros para un campo: pone los espacios al escribir o pegar, no deja entrar
   letras ni simbolos, ni mas numeros que los del formato. El cursor no se mueve de su lugar */
function mascaraNumeros(campo, grupos) {
  const total = grupos.reduce((a, b) => a + b, 0);
  function espaciar() {
    const antes = campo.value.slice(0, campo.selectionStart).replace(/\D/g, '').length;   // numeros antes del cursor
    campo.value = agrupar(campo.value, grupos);
    let pos = 0;
    for (let vistos = 0; pos < campo.value.length && vistos < antes; pos++) if (/\d/.test(campo.value[pos])) vistos++;
    campo.setSelectionRange(pos, pos);
  }
  /* beforeinput: tambien funciona con el teclado del celular. Con una seleccion se deja hacer */
  campo.addEventListener('beforeinput', (e) => {
    const pos = campo.selectionStart;
    if (pos !== campo.selectionEnd) return;
    // Borrar justo despues de un espacio borra el numero de antes (el espacio volveria a aparecer)
    if (e.inputType === 'deleteContentBackward' && campo.value[pos - 1] === ' ') {
      e.preventDefault();
      campo.value = campo.value.slice(0, pos - 2) + campo.value.slice(pos - 1);
      campo.setSelectionRange(pos - 2, pos - 2);
      espaciar();
      return;
    }
    if (!e.inputType.startsWith('insert')) return;
    const nuevo = String(e.data ?? (e.dataTransfer ? e.dataTransfer.getData('text') : ''));
    // Una tecla que no es numero no entra; con el formato completo tampoco (empujaria el ultimo fuera)
    if ((e.inputType === 'insertText' && /\D/.test(nuevo)) ||
        campo.value.replace(/\D/g, '').length + nuevo.replace(/\D/g, '').length > total) e.preventDefault();
  });
  campo.addEventListener('input', espaciar);
}
/* 2026-11-20 -> 20/11/2026 */
const formatoFecha = (iso) => iso.slice(0, 10).split('-').reverse().join('/');
/* 14:30 -> 2:30 PM */
function formatoHora(hhmm) {
  const [h, m] = hhmm.split(':').map(Number);
  return `${h % 12 || 12}:${dos(m)} ${h < 12 ? 'AM' : 'PM'}`;
}

/* "Apellidos, Nombres", como en una ficha clinica */
function nombreCompleto(p) {
  return [p.apellidos, p.nombres].filter(Boolean).join(', ');
}

/* Anos cumplidos a hoy, o null sin fecha */
function edad(nacimiento) {
  if (!nacimiento) return null;
  const [a, m, d] = nacimiento.split('-').map(Number);
  const hoy = new Date();
  const cumplio = hoy.getMonth() + 1 > m || (hoy.getMonth() + 1 === m && hoy.getDate() >= d);
  return hoy.getFullYear() - a - (cumplio ? 0 : 1);
}

/* ---------- tabla ---------- */
export function cargarPacientes() {
  ADMIN.pacientes().then((r) => {
    if (!revisar(r)) return;
    pacientes = r.pacientes.sort(porApellido);
    pintarPacientes();
  }, () => revisar(null));
  sugerirFisios();
}

/* Por apellido y luego nombre; los registros sin nombre al final */
function porApellido(a, b) {
  const na = nombreCompleto(a);
  const nb = nombreCompleto(b);
  if (!na || !nb) return (na ? -1 : 0) + (nb ? 1 : 0) || b.id - a.id;
  return ORDEN.compare(a.apellidos || '', b.apellidos || '') || ORDEN.compare(a.nombres || '', b.nombres || '') || b.id - a.id;
}

/* Los perfiles activos como sugerencia de "Fisioterapeuta responsable" (se puede escribir otro) */
function sugerirFisios() {
  ADMIN.usuarios().then((r) => {
    if (!r || !r.ok) return;   // solo son sugerencias: sin aviso si falla
    porId('listaFisios').innerHTML = r.usuarios.filter((u) => u.activo)
      .map((u) => `<option value="${esc(u.nombre)}"></option>`).join('');
  }, () => {});
}

function citaPasada(proxima) {
  const ahora = new Date();
  return proxima < `${fechaLocal(ahora)} ${dos(ahora.getHours())}:${dos(ahora.getMinutes())}`;
}

function celdaCita(proxima) {
  if (!proxima) return VACIO;
  const pasada = citaPasada(proxima);
  return `<div class="${pasada ? 'text-body-secondary' : 'fw-semibold'}">${formatoFecha(proxima)}</div>` +
    `<div class="text-body-secondary">${formatoHora(proxima.slice(11))}${pasada ? ' · pasada' : ''}</div>`;
}

/* 0-3 verde, 4-6 amarillo, 7-10 rojo */
function insigniaDolor(dolor) {
  if (dolor == null) return VACIO;
  const tono = dolor <= 3 ? 'text-bg-success' : (dolor <= 6 ? 'text-bg-warning' : 'text-bg-danger');
  return `<span class="badge rounded-pill tipo-dato ${tono}">${dolor}/10</span>`;
}

/* Tocar la fila (o el nombre, que es un boton para el teclado) abre la ficha de solo lectura */
function filaPaciente(p) {
  const nombre = nombreCompleto(p);
  const ids = [p.dpi && `DPI ${formatoDpi(p.dpi)}`, p.carne && `Carné ${p.carne}`].filter(Boolean)
    .map((id) => `<span class="text-nowrap">${esc(id)}</span>`).join(' · ');
  const anios = edad(p.nacimiento);
  return `<tr data-ver="${p.id}">` +
    '<td class="ps-3">' +
      `<button type="button" class="btn btn-link p-0 text-start fw-semibold text-break nombre-paciente" data-ver="${p.id}">` +
        `${nombre ? esc(nombre) : '<span class="fst-italic fw-normal text-body-secondary">Sin nombre</span>'}</button>` +
      (ids ? `<div class="tipo-dato small text-body-secondary">${ids}</div>` : '') +
    '</td>' +
    `<td class="tipo-dato text-nowrap">${anios === null ? VACIO : anios}</td>` +
    `<td class="d-none d-md-table-cell tipo-dato small text-nowrap">${p.telefono ? esc(formatoTelefono(p.telefono)) : VACIO}</td>` +
    `<td class="d-none d-lg-table-cell small">${p.fisioterapeuta ? esc(p.fisioterapeuta) : VACIO}</td>` +
    `<td class="d-none d-lg-table-cell">${insigniaDolor(p.dolor)}</td>` +
    `<td class="d-none d-sm-table-cell tipo-dato small text-nowrap">${celdaCita(p.proxima_cita)}</td>` +
    `<td class="d-none d-xl-table-cell tipo-dato small text-nowrap text-body-secondary">${esc(formatoFecha(p.creado))}</td>` +
    '<td class="text-end text-nowrap pe-3">' +
      `<button type="button" class="btn btn-outline-secondary btn-sm me-1" data-editar="${p.id}" aria-label="Editar">${ICONO_EDITAR}</button>` +
      `<button type="button" class="btn btn-outline-danger btn-sm" data-borrar="${p.id}" aria-label="Borrar">${ICONO_BORRAR}</button>` +
    '</td></tr>';
}

/* Cada palabra buscada debe estar en el nombre, el DPI, el carne o el telefono */
function coincide(p, palabras) {
  const texto = sinTildes([p.nombres, p.apellidos, p.carne, p.dpi, p.telefono].filter(Boolean).join(' '));
  return palabras.every((palabra) => texto.includes(palabra));
}

function pintarPacientes() {
  const palabras = sinTildes(buscador.value.trim()).split(/\s+/).filter(Boolean);
  const filas = pacientes.filter((p) => coincide(p, palabras));
  tabla.innerHTML = filas.map(filaPaciente).join('');
  porId('cuentaPacientes').textContent = pacientes.length;
  const vacio = porId('sinPacientes');
  vacio.textContent = pacientes.length ? 'Ningún paciente coincide con la búsqueda.' : 'Todavía no hay registros.';
  vacio.classList.toggle('d-none', filas.length > 0);
}

/* ---------- ficha de solo lectura ---------- */
/* Un dato de la ficha. El texto se escapa; solo `html` (armado aqui, sin datos del usuario sin escapar) entra tal cual */
function datoFicha({ rotulo, texto, html, ancho }) {
  const valor = html || (texto ? esc(texto) : VACIO);
  return `<div class="${ancho ? 'col-12' : 'col-sm-6'}">` +
    `<dt class="tipo-titulo text-uppercase fw-semibold small text-body-secondary mb-1">${rotulo}</dt>` +
    `<dd class="mb-0${ancho ? ' texto-parrafos' : ''}">${valor}</dd></div>`;
}

function seccionFicha(titulo, datos) {
  return `<h3 class="text-uppercase fw-semibold subtitulo-panel text-body-secondary border-top pt-3 mb-3">${titulo}</h3>` +
    `<dl class="row g-3 mb-4">${datos.map(datoFicha).join('')}</dl>`;
}

function abrirFicha(p) {
  enFicha = p;
  const anios = edad(p.nacimiento);
  porId('tFicha').textContent = [p.nombres, p.apellidos].filter(Boolean).join(' ') || 'Sin nombre';
  porId('fichaResumen').textContent = [anios !== null ? `${anios} ${anios === 1 ? 'año' : 'años'}` : null, SEXOS[p.sexo],
    `Registrado el ${formatoFecha(p.creado)} por ${p.creado_por}`].filter(Boolean).join(' · ');
  const textoCita = p.proxima_cita &&
    `${formatoFecha(p.proxima_cita)} · ${formatoHora(p.proxima_cita.slice(11))}${citaPasada(p.proxima_cita) ? ' (pasada)' : ''}`;
  porId('fichaCuerpo').innerHTML =
    seccionFicha('Datos personales', [
      { rotulo: 'Fecha de nacimiento', texto: p.nacimiento && formatoFecha(p.nacimiento) },
      { rotulo: 'Sexo', texto: SEXOS[p.sexo] },
      { rotulo: 'DPI', texto: p.dpi && formatoDpi(p.dpi) },
      { rotulo: 'Carné', texto: p.carne }
    ]) +
    seccionFicha('Contacto', [
      { rotulo: 'Teléfono', texto: p.telefono && formatoTelefono(p.telefono) },
      { rotulo: 'Correo', texto: p.correo },
      { rotulo: 'Contacto de emergencia', texto: p.emergencia_nombre },
      { rotulo: 'Su teléfono', texto: p.emergencia_telefono && formatoTelefono(p.emergencia_telefono) }
    ]) +
    seccionFicha('Medidas', [
      { rotulo: 'Estatura', texto: p.estatura != null && `${p.estatura.toFixed(2)} m` },
      { rotulo: 'Peso', texto: p.peso != null && `${p.peso} lb` }
    ]) +
    seccionFicha('Atención', [
      { rotulo: 'Fisioterapeuta responsable', texto: p.fisioterapeuta },
      { rotulo: 'Dolor (EVA)', html: p.dolor != null && insigniaDolor(p.dolor) },
      { rotulo: 'Próxima cita', texto: textoCita },
      { rotulo: 'Diagnóstico', texto: p.diagnostico, ancho: true },
      { rotulo: 'Notas', texto: p.notas, ancho: true }
    ]);
  abrirModal('modalFicha');
}

/* "Editar" desde la ficha: el panel se abre cuando el modal ya termino de cerrarse */
function editarDesdeFicha() {
  const p = enFicha;
  porId('modalFicha').addEventListener('hidden.bs.modal', () => abrirFormulario(p), { once: true });
  cerrarModal();
}

/* ---------- formulario (panel lateral) ---------- */
/* La edad debajo de la fecha de nacimiento, mientras se escribe */
function mostrarEdad() {
  const anios = edad(campos.nacimiento.value);
  porId('pacEdadTexto').textContent = anios !== null && anios >= 0 ? `${anios} ${anios === 1 ? 'año' : 'años'}` : '';
}

function opcionesCita() {
  const horas = ['<option value="">—</option>'];
  for (let h = 1; h <= 12; h++) horas.push(`<option value="${h}">${h}</option>`);
  cita.hora.innerHTML = horas.join('');
  const minutos = [];
  for (let m = 0; m < 60; m += MINUTOS_CITA) minutos.push(`<option value="${dos(m)}">${dos(m)}</option>`);
  cita.minuto.innerHTML = minutos.join('');
}

/* "AAAA-MM-DD HH:MM" (24 h) -> los cuatro controles, con AM y PM */
function ponerCita(valor) {
  const [fecha, hhmm] = valor ? valor.split(' ') : ['', ''];
  const [h, m] = hhmm ? hhmm.split(':') : ['', '00'];
  cita.fecha.value = fecha;
  cita.hora.value = h === '' ? '' : String(Number(h) % 12 || 12);
  if (![...cita.minuto.options].some((o) => o.value === m)) cita.minuto.add(new Option(m, m));   // hora fuera de los 5 minutos
  cita.minuto.value = m;
  cita.periodo.value = h === '' ? '' : (Number(h) < 12 ? 'AM' : 'PM');
}

/* Los cuatro controles -> "AAAA-MM-DD HH:MM", '' si no hay cita, o [control, aviso] si falta algo */
function leerCita() {
  if (cita.fecha.validity.badInput) return [cita.fecha, 'Esa fecha está incompleta.'];
  const { fecha, hora, minuto, periodo } = Object.fromEntries(Object.entries(cita).map(([k, c]) => [k, c.value]));
  if (!fecha && !hora) return '';
  if (!fecha) return [cita.fecha, 'Elige la fecha de la cita.'];
  if (!hora) return [cita.hora, 'Elige la hora de la cita.'];
  if (!periodo) return [cita.periodo, 'Elige AM o PM.'];
  const h24 = (Number(hora) % 12) + (periodo === 'PM' ? 12 : 0);
  return `${fecha} ${dos(h24)}:${minuto}`;
}

function marcarCita(control, texto) {
  porId(control === cita.fecha ? 'pacCitaFechaAviso' : 'pacCitaHoraAviso').textContent = texto;
  control.classList.add('is-invalid');
  control.focus();
}

function quitarMarcas() {
  [...Object.values(campos), ...Object.values(cita)].forEach((c) => c.classList.remove('is-invalid'));
}

/* Todo lo que hay escrito, para saber si cambio algo desde que se abrio el panel */
function fotoFormulario() {
  return JSON.stringify([...Object.values(campos), ...Object.values(cita)].map((c) => c.value));
}

function llenarFormulario(p) {
  editando = p ? p.id : null;
  for (const [nombre, campo] of Object.entries(campos)) {
    let valor = p ? p[nombre] : null;
    if (valor != null && nombre === 'dpi') valor = formatoDpi(valor);
    if (valor != null && TELEFONOS.includes(nombre)) valor = formatoTelefono(valor);
    campo.value = valor == null ? '' : valor;
  }
  ponerCita(p ? p.proxima_cita : null);
  const hoy = new Date();
  campos.nacimiento.max = fechaLocal(hoy);
  campos.nacimiento.min = `${hoy.getFullYear() - EDAD_MAXIMA}-01-01`;
  quitarMarcas();
  mostrarEdad();
  porId('tituloPaciente').textContent = p ? 'Editar registro' : 'Nuevo registro';
  botonGuardar.textContent = p ? 'Guardar cambios' : 'Guardar';
  original = fotoFormulario();
}

function abrirFormulario(p) {
  llenarFormulario(p);
  panelFormulario.show();
}

/* Cierra sin preguntar (despues de guardar, o al salir de la sesion) */
function cerrarFormulario() {
  const nodo = porId('panelPaciente');
  if (!nodo.classList.contains('show') && !nodo.classList.contains('showing')) return;
  cerrarSinPreguntar = true;
  panelFormulario.hide();
}

/* Cerrar con la X, Cancelar, Esc o tocando fuera: si hay cambios sin guardar, pregunta antes */
function antesDeCerrarFormulario(e) {
  if (cerrarSinPreguntar || fotoFormulario() === original) return;
  e.preventDefault();
  confirmar('¿Descartar cambios?', 'Lo que escribiste en este registro todavía no se ha guardado.', 'Descartar', true, cerrarFormulario);
}

function borrarPaciente(p) {
  const quien = nombreCompleto(p) ? `de ${p.nombres || ''} ${p.apellidos || ''}`.trim() : 'sin nombre';
  confirmar('¿Borrar este registro?', `Se borrará el registro ${quien}. No se puede deshacer.`, 'Borrar', true, () => {
    ADMIN.borrarPaciente(p.id).then((r) => {
      if (!revisar(r)) return;
      mostrarAviso('Registro borrado', 'ok');
      cargarPacientes();
    }, () => revisar(null));
  });
}

function leerFormulario() {
  const datos = {};
  for (const [nombre, campo] of Object.entries(campos)) {
    if (nombre in MEDIDAS) datos[nombre] = campo.value === '' ? null : Number(campo.value);
    else if (PARRAFOS.includes(nombre)) datos[nombre] = campo.value.trim();
    else datos[nombre] = campo.value.trim().replace(/\s+/g, ' ');
  }
  return datos;
}

/* Mensaje si el dato no sirve, o null. Vacio siempre sirve: todo es opcional */
function errorDe(nombre, valor, campo) {
  if (campo.validity.badInput) return 'Ese dato está incompleto o no es válido.';
  if (valor === '' || valor === null) return null;
  if (nombre === 'dpi' && !/^\d{13}$/.test(sinSeparadores(valor))) return 'El DPI tiene 13 números.';
  if (TELEFONOS.includes(nombre) && !/^\d{8}$/.test(sinSeparadores(valor))) return 'El teléfono tiene 8 números.';
  if (nombre === 'correo' && !CORREO.test(valor)) return 'Ese correo no es válido.';
  if (nombre === 'nacimiento') {
    const hoy = new Date();
    if (valor > fechaLocal(hoy)) return 'La fecha de nacimiento no puede ser futura.';
    if (Number(valor.slice(0, 4)) < hoy.getFullYear() - EDAD_MAXIMA) return `La fecha de nacimiento es de hace más de ${EDAD_MAXIMA} años.`;
  }
  if (nombre in MEDIDAS) {
    const [minimo, maximo, decimales, aviso] = MEDIDAS[nombre];
    if (!Number.isFinite(valor) || valor < minimo || valor > maximo || (decimales === 0 && !Number.isInteger(valor))) return aviso;
  }
  return null;
}

function guardarPaciente(e) {
  e.preventDefault();
  quitarMarcas();
  const datos = leerFormulario();
  for (const [nombre, campo] of Object.entries(campos)) {
    const error = errorDe(nombre, datos[nombre], campo);
    if (error) return marcarCampo(campo, error);
  }
  const proxima = leerCita();
  if (Array.isArray(proxima)) return marcarCita(...proxima);
  datos.proxima_cita = proxima;
  if (Object.values(datos).every((v) => v === '' || v === null)) {
    mostrarAviso('Llena al menos un campo.', 'error');
    return campos.nombres.focus();
  }
  botonGuardar.disabled = true;
  ADMIN.guardarPaciente({ id: editando, ...datos }).then((r) => {
    botonGuardar.disabled = false;
    if (r && !r.ok && r.campo === 'proxima_cita') return marcarCita(cita.fecha, r.mensaje);
    if (r && !r.ok && campos[r.campo]) return marcarCampo(campos[r.campo], r.mensaje);
    if (!revisar(r)) return;
    mostrarAviso(editando ? 'Cambios guardados' : 'Registro guardado', 'ok');
    cerrarFormulario();
    cargarPacientes();
  }, () => {
    botonGuardar.disabled = false;
    revisar(null);
  });
}

/* Al salir no quedan datos de pacientes en la pagina */
export function olvidarPacientes() {
  pacientes = [];
  enFicha = null;
  tabla.innerHTML = '';
  buscador.value = '';
  porId('listaFisios').innerHTML = '';
  porId('fichaCuerpo').innerHTML = '';
  cerrarFormulario();
  llenarFormulario(null);
}

export function iniciarPacientes() {
  const nodoPanel = porId('panelPaciente');
  panelFormulario = new bootstrap.Offcanvas(nodoPanel);
  nodoPanel.addEventListener('hide.bs.offcanvas', antesDeCerrarFormulario);
  nodoPanel.addEventListener('hidden.bs.offcanvas', () => {
    cerrarSinPreguntar = false;
    llenarFormulario(null);   // que no queden datos del paciente en el panel cerrado
  });
  opcionesCita();
  llenarFormulario(null);
  porId('btnNuevoPaciente').addEventListener('click', () => abrirFormulario(null));
  porId('btnFichaEditar').addEventListener('click', editarDesdeFicha);
  porId('btnFichaCerrar').addEventListener('click', cerrarModal);
  buscador.addEventListener('input', pintarPacientes);
  formulario.addEventListener('submit', guardarPaciente);
  campos.nacimiento.addEventListener('input', mostrarEdad);
  mascaraNumeros(campos.dpi, GRUPOS_DPI);
  TELEFONOS.forEach((nombre) => mascaraNumeros(campos[nombre], GRUPOS_TELEFONO));
  tabla.addEventListener('click', (e) => {
    const boton = e.target.closest('[data-editar], [data-borrar], [data-ver]');
    if (!boton) return;
    const id = parseInt(boton.dataset.editar || boton.dataset.borrar || boton.dataset.ver, 10);
    const paciente = pacientes.find((p) => p.id === id);
    if (!paciente) return;
    if (boton.dataset.editar) abrirFormulario(paciente);
    else if (boton.dataset.borrar) borrarPaciente(paciente);
    else abrirFicha(paciente);
  });
}
