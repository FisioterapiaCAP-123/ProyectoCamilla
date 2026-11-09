/* Quien tiene el control y como se pasa de una persona a otra. */
import { SERVIDOR } from '../api/ordenes.js';
import { ESPERA_RESPUESTA, ESPERA_SOLICITUD } from '../config.js';
import { detenerTodo } from '../camilla/movimiento.js';
import { control, panel, sesion } from '../estado.js';
import { mostrarAviso } from '../ui/avisos.js';
import { abrirModal, cerrarModal, detenerCuenta, iniciarCuenta } from '../ui/modales.js';
import { pintar } from '../ui/pintado.js';
import { porId } from '../utilidades.js';

let solicitudEntrante = null;
let solicitudVista = null;

export function aplicarControl(datos) {
  const teniaYo = control.soyYo;
  control.titular = datos.titular || null;
  control.usuario = datos.usuario || null;
  control.soyYo = Boolean(control.usuario) && control.usuario === sesion.usuario;

  if (control.soyYo && (panel.modalActivo === 'modalEsperando' || panel.modalActivo === 'modalTomar')) cerrarModal();

  if (!teniaYo && control.soyYo) mostrarAviso('Ahora tienes el control de la camilla', 'ok');
  if (teniaYo && !control.soyYo) {
    detenerTodo();
    mostrarAviso(control.titular ? 'Cediste el control a ' + control.titular : 'Ya no tienes el control', 'info');
  }
  pintar();
}

export function olvidarControl() {
  solicitudEntrante = null;
  control.titular = null;
  control.usuario = null;
  control.soyYo = false;
  control.conectado = true;
}

export function pedirControl() {
  porId('solicitarNombre').textContent = control.titular || '';
  abrirModal('modalSolicitar');
}

function abrirEntrante(solicitud) {
  solicitudEntrante = solicitud;
  porId('entranteNombre').textContent = solicitud.usuario;
  abrirModal('modalEntrante');
  iniciarCuenta(ESPERA_RESPUESTA, porId('entranteSegundos'), porId('entranteBarra'), () => {
    cerrarModal();
    SERVIDOR.responderSolicitud(solicitudEntrante, false);
    mostrarAviso('No respondiste a tiempo. Sigues con el control.', 'info');
    solicitudEntrante = null;
  });
}

/* {solicitud:{id, usuario}}: alguien me pide el control, o ya dejo de pedirlo */
export function atenderSolicitud(solicitud) {
  if (solicitud && solicitud.id !== solicitudVista) {
    solicitudVista = solicitud.id;
    abrirEntrante(solicitud);
  } else if (!solicitud && solicitudEntrante && panel.modalActivo === 'modalEntrante') {
    cerrarModal();
    mostrarAviso(solicitudEntrante.usuario + ' ya no pide el control', 'info');
    solicitudEntrante = null;
  }
}

/* {respuesta:{aceptada, usuario}}: contestaron mi pedido */
export function resolverSolicitud(respuesta) {
  detenerCuenta();
  if (panel.modalActivo === 'modalEsperando') cerrarModal();
  if (respuesta.aceptada) mostrarAviso('Te pasaron el control', 'ok');
  else mostrarAviso((respuesta.usuario || 'El operador') + ' no te pasó el control', 'error');
}

function solicitarAlTitular() {
  SERVIDOR.solicitarControl().then((r) => {
    if (r && r.ok) return;   // el aviso le llega al titular en su proxima consulta
    if (panel.modalActivo === 'modalEsperando') cerrarModal();
    mostrarAviso((r && r.mensaje) || 'No se pudo pedir el control', 'error');
  });
  porId('esperandoNombre').textContent = control.titular || '';
  abrirModal('modalEsperando');
  iniciarCuenta(ESPERA_SOLICITUD, porId('esperandoSegundos'), porId('esperandoBarra'), () => {
    cerrarModal();
    SERVIDOR.cancelarSolicitud();
    mostrarAviso('No hubo respuesta. Sigues en solo lectura.', 'error');
  });
}

function responderEntrante(aceptar) {
  SERVIDOR.responderSolicitud(solicitudEntrante, aceptar);
  cerrarModal();
  solicitudEntrante = null;
}

export function iniciarCesion() {
  porId('controlAcciones').addEventListener('click', (e) => {
    const boton = e.target.closest('[data-accion]');
    if (!boton) return;
    if (boton.dataset.accion === 'tomar') abrirModal('modalTomar');
    if (boton.dataset.accion === 'solicitar') pedirControl();
    if (boton.dataset.accion === 'liberar') SERVIDOR.liberarControl();
  });

  porId('btnTomarControl').addEventListener('click', () => {
    cerrarModal();
    SERVIDOR.tomarControl().then((r) => {
      if (r && !r.ok) mostrarAviso(r.mensaje || 'No se pudo tomar el control', 'error');
    });
  });
  porId('btnTomarNo').addEventListener('click', cerrarModal);

  porId('btnSolicitarControl').addEventListener('click', solicitarAlTitular);
  porId('btnSolicitarNo').addEventListener('click', cerrarModal);
  porId('btnCancelarSolicitud').addEventListener('click', () => {
    SERVIDOR.cancelarSolicitud();
    cerrarModal();
  });

  porId('btnPermitir').addEventListener('click', () => responderEntrante(true));
  porId('btnDenegar').addEventListener('click', () => {
    responderEntrante(false);
    mostrarAviso('Denegaste la solicitud. Sigues con el control.', 'info');
  });
}
