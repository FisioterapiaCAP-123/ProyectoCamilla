/* Aplica al panel lo que informa el servidor. El sondeo (api/sondeo.js) le entrega cada respuesta. */
import { guardarToken, leerLlave } from './api/cliente.js';
import { SERVIDOR } from './api/ordenes.js';
import { activarParo, detenerTodo, liberarParo } from './camilla/movimiento.js';
import { aplicarAngulos } from './camilla/telemetria.js';
import { control, panel, sesion } from './estado.js';
import { abrirModal, cerrarModal } from './ui/modales.js';
import { pintar } from './ui/pintado.js';
import { registrar } from './ui/registro.js';
import { porId } from './utilidades.js';
import { aplicarControl, atenderSolicitud, resolverSolicitud } from './vistas/cesion.js';
import { aplicarRol } from './vistas/pestanas.js';
import { actualizarRegistros } from './vistas/pin.js';
import { avisoLogin } from './vistas/acceso.js';
import { entrarAlPanel, reanudarEquipo, sesionTerminada } from './vistas/sesion.js';

const ECO_MS = 1500;   // tras pulsar el paro se ignora lo que diga el servidor, que aun no lo refleja

const vistaPanel = porId('vistaPanel');

let reanudar = Boolean(sesion.token || leerLlave());
let retomar = false;   // al despertar o reconectar, el equipo recordado retoma el control si esta libre

export function retomarControl() {
  if (leerLlave()) retomar = true;
}

export function recibir(e) {
  if (reanudar) {
    reanudar = false;
    if (e.usuario) entrarAlPanel(e, e.control);
    else {
      guardarToken('');
      if (e.cerrada) avisoLogin(e.cerrada, 'error');   // la cerro otro: no se vuelve a entrar solo
      else reanudarEquipo();
    }
    return;
  }
  if (sesion.usuario && !e.usuario) {
    sesionTerminada(e.cerrada);
    return;
  }

  // El paro lo puede disparar cualquier dispositivo
  if (Boolean(e.paro) !== panel.paro && Date.now() - panel.paroPedidoEn > ECO_MS) {
    if (e.paro) activarParo(true);
    else liberarParo(true);
  }
  if (vistaPanel.hidden) return;

  // Si el ESP32 se desconecta, el panel lo muestra y deja de permitir el movimiento
  if (e.hardware) {
    const equipo = { conectado: e.hardware.conectado, secciones: e.hardware.secciones };
    if (JSON.stringify(equipo) !== JSON.stringify(panel.hardware)) {
      panel.hardware = equipo;
      registrar('← motores: ' + (equipo.conectado ? equipo.secciones.join(', ') : 'sin conexión'));
      pintar();
    }
    recibirSensores(e.hardware.sensores || {});
    recibirAltura(e.hardware.altura || null);
  }
  if (e.vuelta_altura) recibirVuelta(e.vuelta_altura);

  // El administrador puede cambiar el rol mientras la pagina esta abierta
  if (e.rol !== sesion.rol) aplicarRol(e.rol);
  actualizarRegistros(e.registros);   // PIN de la tablet

  if ((e.control.usuario || null) !== control.usuario) {
    registrar(`← control: ${e.control.titular || 'nadie'}  (yo: ${sesion.usuario})`);
    aplicarControl(e.control);
  }
  // Si otro lo tiene se respeta: se pide como siempre
  if (retomar) {
    retomar = false;
    if (!e.control.usuario) {
      registrar('EQUIPO RECORDADO: control libre, se retoma');
      SERVIDOR.tomarControl();
    }
  }

  atenderSolicitud(e.solicitud);
  if (e.respuesta) resolverSolicitud(e.respuesta);

  // Angulo real de las secciones con sensor: siempre, tambien mientras se mueven
  if (e.telemetria) aplicarAngulos(e.telemetria);
}

/* El estado de cada sensor (no el angulo, que cambia todo el tiempo) va al registro */
function recibirSensores(sensores) {
  let cambio = false;
  ['cabeza', 'piernas'].forEach((s) => {
    const antes = panel.sensores[s] ? panel.sensores[s].estado : 'sin sensor';
    const ahora = sensores[s] ? sensores[s].estado : 'sin sensor';
    if (antes !== ahora) {
      registrar('← sensor de ' + s + ': ' + ahora);
      cambio = true;
    }
  });
  panel.sensores = sensores;
  if (cambio) pintar();
}

/* Pasos de la altura: el modo, el centro y los topes van al registro; los pasos solo a la pantalla */
function recibirAltura(altura) {
  const resumen = (a) => (a ? `${a.modo}, ${a.centro ? 'con' : 'sin'} centro, topes ${a.topes.abajo} / ${a.topes.arriba}` : 'sin datos');
  const antes = panel.altura;
  if (resumen(antes) !== resumen(altura)) registrar('← altura: ' + resumen(altura));
  if (JSON.stringify(antes) === JSON.stringify(altura)) return;
  panel.altura = altura;
  pintar();
}

/* "Volver al centro sola": el interruptor y cuando empieza o termina la vuelta van al registro */
function recibirVuelta(vuelta) {
  const antes = panel.vuelta;
  if (antes.activa !== vuelta.activa) registrar('← vuelta sola al centro: ' + (vuelta.activa ? 'prendida' : 'apagada'));
  if (antes.volviendo !== vuelta.volviendo) registrar('← altura ' + (vuelta.volviendo ? 'volviendo sola al centro' : 'dejó de volver al centro'));
  if (JSON.stringify(antes) === JSON.stringify(vuelta)) return;
  panel.vuelta = vuelta;
  pintar();
}

export function reconectado() {
  if (control.conectado) return;
  control.conectado = true;
  retomarControl();
  registrar('CONEXIÓN RECUPERADA');
  if (panel.modalActivo === 'modalSinConexion') cerrarModal();
  pintar();
}

export function caidaDeConexion() {
  if (!control.conectado) return;
  control.conectado = false;
  detenerTodo();
  registrar('CONEXIÓN PERDIDA');
  if (!vistaPanel.hidden) abrirModal('modalSinConexion');
  pintar();
}
