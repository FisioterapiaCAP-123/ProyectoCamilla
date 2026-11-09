/* Entrar y salir del panel. */
import { guardarToken } from '../api/cliente.js';
import { SERVIDOR } from '../api/ordenes.js';
import { consultar } from '../api/sondeo.js';
import { detenerTodo } from '../camilla/movimiento.js';
import { control, sesion } from '../estado.js';
import { borrarAvisos } from '../ui/avisos.js';
import { cerrarModal } from '../ui/modales.js';
import { pintar } from '../ui/pintado.js';
import { registrar } from '../ui/registro.js';
import { porId } from '../utilidades.js';
import { avisoLogin, reiniciarAcceso } from './acceso.js';
import { aplicarControl, olvidarControl, pedirControl } from './cesion.js';
import { olvidarPacientes } from './pacientes.js';
import { aplicarRol } from './pestanas.js';
import { olvidarUsuarios } from './usuarios.js';

const vistaLogin = porId('vistaLogin');
const vistaPanel = porId('vistaPanel');

/* perfil = {usuario, nombre, rol}: llega del login, del registro o al recargar la pagina */
export function entrarAlPanel(perfil, estadoControl, token) {
  sesion.usuario = perfil.usuario;
  sesion.nombre = perfil.nombre || perfil.usuario;
  if (token) guardarToken(token);
  vistaLogin.hidden = true;
  vistaPanel.hidden = false;
  reiniciarAcceso();
  porId('perfilNombre').textContent = sesion.nombre;
  porId('perfilInicial').textContent = sesion.nombre.charAt(0).toUpperCase();
  aplicarRol(perfil.rol);
  registrar(`SESION INICIADA  usuario=${sesion.usuario}  rol=${sesion.rol}`);

  consultar();
  aplicarControl(estadoControl || { titular: null, usuario: null });

  /* Si no lo tiene nadie, el que entra se queda con el control.
     Si ya lo tiene otro, entra en solo lectura y se le ofrece pedirlo. */
  if (!control.usuario) SERVIDOR.tomarControl();   // el resultado llega con la consulta de estado
  else if (!control.soyYo) pedirControl();
  pintar();
}

function salirDelPanel() {
  detenerTodo();
  cerrarModal();
  registrar('SESION CERRADA  usuario=' + sesion.usuario);
  guardarToken('');
  sesion.usuario = null;
  sesion.nombre = null;
  aplicarRol(null);
  olvidarPacientes();   // que no queden datos de pacientes en la pagina
  olvidarUsuarios();
  borrarAvisos();       // ni avisos de la sesion anterior
  olvidarControl();
  vistaPanel.hidden = true;
  vistaLogin.hidden = false;
  reiniciarAcceso();
  pintar();
}

function cerrarSesion() {
  detenerTodo();
  SERVIDOR.logout();   // el servidor libera el control si lo tenia
  salirDelPanel();
}

/* El servidor ya no conoce la sesion (se reinicio, entro desde otro dispositivo o lo desactivaron) */
export function sesionTerminada() {
  registrar('SESION VENCIDA');
  salirDelPanel();
  avisoLogin('Tu sesión terminó. Vuelve a iniciar sesión.', 'error');
}

export function iniciarSalida() {
  porId('btnSalir').addEventListener('click', cerrarSesion);
}
