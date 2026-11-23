/* PIN del equipo recordado (la tablet de control).

   En un equipo recordado de un administrador, Registros y Usuarios se abren con un PIN
   de 4 numeros y se cierran solos: a los 30 min sin tocar nada en ellos, al apagarse la
   pantalla o al volver a Control. Mover la camilla nunca pide PIN.
   El servidor lo hace cumplir (servidor.py, /api/pin/*): sin abrir, no entrega datos.
   /api/estado trae registros = {pin, abierto, pide_clave}, o null si este equipo no usa PIN. */
import { llamar } from '../api/cliente.js';
import { panel, sesion } from '../estado.js';
import { mostrarAviso } from '../ui/avisos.js';
import { marcarCampo, ocupado } from '../ui/formularios.js';
import { abrirModal, cerrarModal } from '../ui/modales.js';
import { registrar } from '../ui/registro.js';
import { porId } from '../utilidades.js';
import { olvidarPacientes } from './pacientes.js';
import { olvidarUsuarios } from './usuarios.js';

const CIERRE_MS = 30 * 60 * 1000;   // sin uso: se cierran (el servidor da 1 min mas)
const SEGUIR_MS = 60 * 1000;        // cada cuanto se le avisa al servidor que se siguen usando
const PIN = /^\d{4}$/;

const campos = { clave: porId('pinClave'), pin: porId('pinNuevo'), repite: porId('pinRepite') };
const botonOk = porId('btnPinOk');

const ECO_MS = 3000;
let abierto = false;      // Registros y Usuarios abiertos en este equipo
let abiertoEn = 0;
let ultimoUso = 0;
let ultimoSeguir = 0;
let modo = 'abrir';       // 'abrir' o 'crear'
let alAbrir = null;       // lo que se iba a mostrar cuando se pidio el PIN
let irAControl = () => {};

export function pidePin() {
  return Boolean(sesion.registros);
}

/* Lo que llega en cada consulta de estado */
export function actualizarRegistros(registros) {
  const antes = sesion.registros;
  sesion.registros = registros || null;
  if (!registros) {
    abierto = false;
    return;
  }
  if (!antes && registros.abierto) {   // acaba de entrar con contrasena: empieza abierto
    abierto = true;
    usado();
  }
  // El servidor los cerro (o nunca los abrio): fuera de Registros. Justo despues de abrir
  // puede llegar una consulta que salio antes: esa no cuenta
  if (!registros.abierto && (abierto || panel.pestana !== 'control') && Date.now() - abiertoEn > ECO_MS) vencer();
}

/* Al salir de la sesion */
export function olvidarPin() {
  abierto = false;
  alAbrir = null;
  sesion.registros = null;
}

function usado() {
  ultimoUso = Date.now();
}

/* Antes de mostrar Registros o Usuarios. continuar() los muestra */
export function pedirAcceso(continuar) {
  if (!pidePin()) return continuar();
  if (sesion.registros.pin && abierto) {
    usado();
    return continuar();
  }
  alAbrir = continuar;
  mostrarModal(sesion.registros.pin ? 'abrir' : 'crear');
}

/* Cierra Registros y Usuarios y borra sus datos de la pagina. Lo llama tambien quien va a Control */
export function bloquear() {
  if (!pidePin() || !abierto) return;
  abierto = false;
  llamar('/api/pin/cerrar').catch(() => {});
  olvidarPacientes();
  olvidarUsuarios();
  registrar('REGISTROS BLOQUEADOS');
}

/* Se cumplio el tiempo, se apago la pantalla o el servidor los cerro */
function vencer(aviso) {
  if (panel.pestana !== 'control') irAControl();   // ir a Control ya los bloquea
  else bloquear();
  if (aviso) mostrarAviso(aviso, 'info');
}

function mostrarModal(cual) {
  modo = cual;
  const crear = cual === 'crear';
  const pideClave = crear && sesion.registros.pide_clave;
  porId('tPin').textContent = crear ? 'Crea tu PIN' : 'Registros bloqueado';
  porId('pinTexto').textContent = crear
    ? 'Con este PIN se abren Registros y Usuarios en este equipo. Se bloquean solos tras 30 minutos sin uso.' +
      (pideClave ? ' Para crearlo escribe también tu contraseña.' : '')
    : 'Ingresa tu PIN de 4 números.';
  porId('pinRotulo').textContent = crear ? 'PIN nuevo (4 números)' : 'PIN';
  porId('pinClaveGrupo').hidden = !pideClave;
  porId('pinRepiteGrupo').hidden = !crear;
  porId('btnPinOlvide').hidden = crear;
  botonOk.dataset.texto = crear ? 'Guardar PIN' : 'Abrir';
  ocupado(botonOk);
  Object.values(campos).forEach((c) => { c.value = ''; c.classList.remove('is-invalid'); });
  abrirModal('modalPin');
  setTimeout(() => (pideClave ? campos.clave : campos.pin).focus(), 300);
}

function listo() {
  abierto = true;
  abiertoEn = Date.now();
  usado();
  ultimoSeguir = Date.now();
  if (sesion.registros) sesion.registros.pin = true;
  cerrarModal();
  const continuar = alAbrir;
  alAbrir = null;
  if (continuar) continuar();
}

function enviarPin(e) {
  e.preventDefault();
  Object.values(campos).forEach((c) => c.classList.remove('is-invalid'));
  const crear = modo === 'crear';
  const pideClave = crear && sesion.registros.pide_clave;
  if (pideClave && !campos.clave.value) return marcarCampo(campos.clave, 'Escribe tu contraseña.');
  if (!PIN.test(campos.pin.value)) return marcarCampo(campos.pin, 'El PIN debe tener 4 dígitos.');
  if (crear && campos.repite.value !== campos.pin.value) return marcarCampo(campos.repite);

  const datos = { pin: campos.pin.value };
  if (pideClave) datos.clave = campos.clave.value;
  ocupado(botonOk, crear ? 'Guardando...' : 'Abriendo...');
  llamar(crear ? '/api/pin/crear' : '/api/pin/abrir', datos, 8000).then((r) => {
    ocupado(botonOk);
    if (r && r.ok) {
      if (crear) mostrarAviso('PIN guardado', 'ok');
      return listo();
    }
    if (r && r.sin_pin) return mostrarModal('crear');
    campos.pin.value = '';
    campos.repite.value = '';
    if (r && r.campo === 'clave') return marcarCampo(campos.clave, r.mensaje);
    marcarCampo(campos.pin, (r && r.mensaje) || 'No se pudo contactar con la camilla.');
  }, () => {
    ocupado(botonOk);
    marcarCampo(campos.pin, 'No se pudo contactar con la camilla.');
  });
}

/* Tocar o escribir dentro de Registros o Usuarios los mantiene abiertos */
function actividad() {
  if (!abierto || panel.pestana === 'control') return;
  usado();
  if (Date.now() - ultimoSeguir < SEGUIR_MS) return;
  ultimoSeguir = Date.now();
  llamar('/api/pin/seguir').then((r) => { if (r && !r.ok) vencer('Registros se bloqueó por seguridad. Ingresa tu PIN para abrirlo.'); }, () => {});
}

/* funciones.irAControl: muestra la pestana Control (y con eso llama a bloquear) */
export function iniciarPin(funciones) {
  irAControl = funciones.irAControl;
  porId('formPin').addEventListener('submit', enviarPin);
  porId('btnPinCancelar').addEventListener('click', () => {
    alAbrir = null;
    cerrarModal();
  });
  porId('btnPinOlvide').addEventListener('click', () => mostrarModal('crear'));
  Object.values(campos).forEach((c) => c.addEventListener('input', () => c.classList.remove('is-invalid')));
  [campos.pin, campos.repite].forEach((c) => c.addEventListener('input', () => { c.value = c.value.replace(/\D/g, '').slice(0, 4); }));

  ['pointerdown', 'keydown'].forEach((tipo) => document.addEventListener(tipo, actividad, true));
  setInterval(() => {
    if (abierto && Date.now() - ultimoUso > CIERRE_MS) vencer('Registros se bloqueó por 30 minutos sin uso.');
  }, 10000);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden && pidePin() && abierto) vencer();
  });
}
