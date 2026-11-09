/* Salida de datos: lo que el panel le manda al servidor. */
import { MANTENER_MS } from '../config.js';
import { panel } from '../estado.js';
import { enviar, llamar } from './cliente.js';
import { consultar } from './sondeo.js';

let mantenerId = null;

/* Ordenes de control: despues se pregunta el estado ya, sin esperar al segundo */
function enviarControl(ruta, datos) {
  return enviar(ruta, datos).then((r) => { consultar(); return r; });
}

export const SERVIDOR = {
  // POST /api/login   {usuario, clave}
  //   -> {ok:true, usuario:"usuario1", nombre:"Persona", rol:"admin"|"fisio", sesion:"token",
  //       control:{titular:"Persona"|null, usuario:"usuario1"|null}}
  //   -> {ok:false, mensaje:"..."}
  login(usuario, clave) {
    return llamar('/api/login', { usuario, clave }, 8000);
  },
  // POST /api/registro {usuario, nombre, clave}   perfil nuevo (fisioterapeuta) y entra
  //   -> igual que login, o {ok:false, campo:"usuario"|"nombre"|"clave", mensaje:"..."}
  registro(usuario, nombre, clave) {
    return llamar('/api/registro', { usuario, nombre, clave }, 8000);
  },

  // POST /api/logout          libera el control si lo tenia
  logout() { return enviar('/api/logout'); },

  // POST /api/mover {seccion, dir}         arranca el motor
  // Se repite mientras se mantiene el boton: si deja de llegar (WiFi caido,
  // pagina cerrada) el servidor para el motor solo en 1 s.
  mover(seccion, dir) {
    clearInterval(mantenerId);
    panel.ultimaOrden = Date.now();
    enviar('/api/mover', { seccion, dir });
    mantenerId = setInterval(() => {
      panel.ultimaOrden = Date.now();
      llamar('/api/mover', { seccion, dir }).catch(() => {});
    }, MANTENER_MS);
  },
  // POST /api/paso {seccion, grados}       un grado exacto
  paso(seccion, dir) {
    panel.ultimaOrden = Date.now();
    enviar('/api/paso', { seccion, grados: dir });
  },
  // POST /api/detener {seccion}
  detener(seccion) {
    clearInterval(mantenerId);
    mantenerId = null;
    enviar('/api/detener', { seccion });
  },
  // POST /api/paro {activo}                no requiere tener el control ni haber entrado
  paro(activo) {
    panel.paroPedidoEn = Date.now();
    enviar('/api/paro', { activo });
  },

  // POST /api/control/tomar                solo si no lo tiene nadie
  tomarControl() { return enviarControl('/api/control/tomar'); },
  // POST /api/control/solicitar            el servidor avisa al titular
  solicitarControl() { return enviarControl('/api/control/solicitar'); },
  // POST /api/control/cancelar
  cancelarSolicitud() { return enviarControl('/api/control/cancelar'); },
  // POST /api/control/responder {id, aceptar}
  responderSolicitud(solicitud, aceptar) {
    return enviarControl('/api/control/responder', { id: solicitud ? solicitud.id : null, aceptar: Boolean(aceptar) });
  },
  // POST /api/control/liberar
  liberarControl() { return enviarControl('/api/control/liberar'); }
};
