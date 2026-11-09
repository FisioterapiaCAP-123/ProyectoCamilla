/* Aplica al panel lo que informa el servidor. El sondeo (api/sondeo.js) le entrega cada respuesta. */
import { guardarToken } from './api/cliente.js';
import { activarParo, detenerTodo, liberarParo } from './camilla/movimiento.js';
import { aplicarAngulos } from './camilla/telemetria.js';
import { control, panel, sesion } from './estado.js';
import { abrirModal, cerrarModal } from './ui/modales.js';
import { pintar } from './ui/pintado.js';
import { registrar } from './ui/registro.js';
import { porId } from './utilidades.js';
import { aplicarControl, atenderSolicitud, resolverSolicitud } from './vistas/cesion.js';
import { aplicarRol } from './vistas/pestanas.js';
import { entrarAlPanel, sesionTerminada } from './vistas/sesion.js';

const ECO_MS = 1500;   // tras una orden propia se ignora lo que diga el servidor, que aun no la refleja

const vistaPanel = porId('vistaPanel');

let reanudar = Boolean(sesion.token);   // al recargar la pagina se vuelve a entrar con la misma sesion

export function recibir(e) {
  if (reanudar) {
    reanudar = false;
    if (e.usuario) entrarAlPanel(e, e.control);
    else guardarToken('');
    return;
  }
  if (sesion.usuario && !e.usuario) {
    sesionTerminada();
    return;
  }

  // El paro lo puede disparar cualquier dispositivo
  if (Boolean(e.paro) !== panel.paro && Date.now() - panel.paroPedidoEn > ECO_MS) {
    if (e.paro) activarParo(true);
    else liberarParo(true);
  }
  if (vistaPanel.hidden) return;

  // Si el ESP32 se desconecta, el panel lo muestra y deja de permitir el movimiento
  if (e.hardware && JSON.stringify(e.hardware) !== JSON.stringify(panel.hardware)) {
    panel.hardware = e.hardware;
    registrar('← motores: ' + (e.hardware.conectado ? e.hardware.secciones.join(', ') : 'sin conexión'));
    pintar();
  }

  // El administrador puede cambiar el rol mientras la pagina esta abierta
  if (e.rol !== sesion.rol) aplicarRol(e.rol);

  if ((e.control.usuario || null) !== control.usuario) {
    registrar(`← control: ${e.control.titular || 'nadie'}  (yo: ${sesion.usuario})`);
    aplicarControl(e.control);
  }

  atenderSolicitud(e.solicitud);
  if (e.respuesta) resolverSolicitud(e.respuesta);

  // Mientras yo muevo manda lo que se ve en mi pantalla
  if (e.telemetria && !panel.manual && !panel.destino && Date.now() - panel.ultimaOrden > ECO_MS) {
    aplicarAngulos(e.telemetria);
  }
}

export function reconectado() {
  if (control.conectado) return;
  control.conectado = true;
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
