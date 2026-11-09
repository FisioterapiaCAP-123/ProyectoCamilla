/* Punto de entrada del panel: conecta los modulos y arranca. */
import { consultar, iniciarSondeo } from './api/sondeo.js';
import { iniciarMandos } from './camilla/mandos.js';
import { exponerApi } from './camilla/telemetria.js';
import { caidaDeConexion, reconectado, recibir } from './recepcion.js';
import { iniciarModales } from './ui/modales.js';
import { pintar, prepararEscalas } from './ui/pintado.js';
import { iniciarDiagnostico, registrar } from './ui/registro.js';
import { porId } from './utilidades.js';
import { iniciarAcceso } from './vistas/acceso.js';
import { iniciarCesion } from './vistas/cesion.js';
import { iniciarPacientes } from './vistas/pacientes.js';
import { iniciarPestanas } from './vistas/pestanas.js';
import { entrarAlPanel, iniciarSalida } from './vistas/sesion.js';
import { iniciarUsuarios } from './vistas/usuarios.js';

iniciarDiagnostico();
iniciarModales();
iniciarMandos();
iniciarCesion();
iniciarAcceso(entrarAlPanel);
iniciarSalida();
iniciarPestanas();
iniciarPacientes();
iniciarUsuarios();
exponerApi();

porId('btnReintentar').addEventListener('click', () => {
  registrar('REINTENTANDO CONEXIÓN');
  consultar();
});

prepararEscalas();
registrar('PANEL INICIADO');
pintar();
iniciarSondeo({ alRecibir: recibir, alCaer: caidaDeConexion, alRecuperar: reconectado });
