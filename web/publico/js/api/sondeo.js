/* Entrada de datos: pregunta GET /api/estado cada segundo.

   Es el unico modulo que sabe COMO llegan los datos del servidor. Quien los
   usa solo entrega sus tres funciones a iniciarSondeo().

   GET /api/estado responde:
     { usuario:"usuario1"|null,         null si la sesion ya no existe
       nombre:"Persona", rol:"admin"|"fisio",
       control:{titular:"Persona"|null, usuario:"usuario1"|null},
       paro:false, simulacion:true,
       solicitud:{id, usuario}|null,    solo le llega al titular
       respuesta:{aceptada, usuario}|null,   solo al que pidio, una vez
       telemetria:{cabeza:32, piernas:14} } */
import { CONSULTA_MS, FALLOS_PARA_CAIDA } from '../config.js';
import { sesion } from '../estado.js';
import { registrar } from '../ui/registro.js';
import { pedir } from './cliente.js';

const PLAZO_MS = 2500;

let oyentes = { alRecibir() {}, alCaer() {}, alRecuperar() {} };
let fallos = 0;
let consultando = false;
let consultas = 0;

export function consultar() {
  if (consultando) return;
  consultando = true;
  const token = sesion.token;
  pedir('/api/estado', { headers: { 'X-Sesion': token }, cache: 'no-store' }, PLAZO_MS)
    .then((e) => {
      consultando = false;
      fallos = 0;
      oyentes.alRecuperar();
      if (sesion.usuario && ++consultas % 10 === 1) {   // diagnostico: una de cada 10 consultas
        registrar('← estado #' + consultas + ': ' + (e.usuario || 'sin sesion') + ' / control ' +
                  ((e.control && e.control.titular) || 'nadie') + (token === sesion.token ? '' : ' (vieja)'));
      }
      if (token !== sesion.token) return;   // la sesion cambio mientras tanto: respuesta vieja
      try { oyentes.alRecibir(e); } catch (err) { registrar('ERROR al leer el estado: ' + err.message); }
    }, () => {
      consultando = false;
      if (++fallos >= FALLOS_PARA_CAIDA) oyentes.alCaer();
    });
}

/* Tambien corre en el login: el paro se ve aunque nadie haya entrado */
export function iniciarSondeo(funciones) {
  oyentes = funciones;
  consultar();
  setInterval(consultar, CONSULTA_MS);
}
