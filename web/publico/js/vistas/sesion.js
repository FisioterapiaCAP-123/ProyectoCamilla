/* Entrar y salir del panel. */
import { guardarLlave, guardarToken, leerLlave } from '../api/cliente.js';
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
import { olvidarPin } from './pin.js';
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
  olvidarPin();
  borrarAvisos();       // ni avisos de la sesion anterior
  olvidarControl();
  vistaPanel.hidden = true;
  vistaLogin.hidden = false;
  reiniciarAcceso();
  pintar();
}

function cerrarSesion() {
  detenerTodo();
  SERVIDOR.logout();   // el servidor libera el control si lo tenia, y olvida este equipo
  guardarLlave('');
  salirDelPanel();
}

/* Equipo recordado (la tablet de control): vuelve a entrar con su llave, sin contrasena.
   Devuelve una promesa: true si entro. Si el servidor rechaza la llave (se entro desde otro
   equipo, Salir, contrasena nueva, perfil desactivado o 30 dias sin uso) se borra */
export function reanudarEquipo() {
  const llave = leerLlave();
  if (!llave) return Promise.resolve(false);
  registrar('EQUIPO RECORDADO: volviendo a entrar');
  return SERVIDOR.reanudar(llave).then((r) => {
    if (r && r.ok) {
      entrarAlPanel(r, r.control, r.sesion);
      return true;
    }
    if (r) guardarLlave('');
    return false;
  }, () => false);
}

/* El servidor ya no conoce la sesion.
   cerrada: por que la cerro otro (se abrio en otro equipo o pestana, perfil desactivado o borrado).
   Entonces no se vuelve a entrar solo: dos pestanas con la misma llave se sacarian entre si sin parar.
   Sin motivo (se reinicio la Raspberry o vencio) un equipo recordado vuelve a entrar */
export function sesionTerminada(cerrada) {
  registrar('SESION VENCIDA' + (cerrada ? ': ' + cerrada : ''));
  salirDelPanel();
  if (cerrada) {
    avisoLogin(cerrada, 'error');
    return;
  }
  reanudarEquipo().then((entro) => {
    if (!entro) avisoLogin('Tu sesión terminó. Vuelve a iniciar sesión.', 'error');
  });
}

export function iniciarSalida() {
  porId('btnSalir').addEventListener('click', cerrarSesion);
}
