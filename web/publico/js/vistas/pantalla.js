/* Pantalla completa en la tablet de control.

   En un equipo tactil recordado ("Recordar este equipo"), cada toque pide pantalla completa
   si no la tiene: asi no se ven la barra de Android (con su aviso "sin internet") ni la
   barra de direcciones de Chrome. Android la quita al apagarse la pantalla; el siguiente
   toque la recupera. La laptop y los equipos no recordados no cambian.
   Se usa 'click' y no 'pointerdown': el cambio de tamano llega despues del toque y no
   mueve el boton que se esta presionando. */
import { leerLlave } from '../api/cliente.js';

const tactil = window.matchMedia('(pointer: coarse)');

function pedirPantallaCompleta() {
  if (document.fullscreenElement || !document.fullscreenEnabled) return;
  if (!tactil.matches || !leerLlave()) return;
  document.documentElement.requestFullscreen({ navigationUI: 'hide' }).catch(() => {});
}

export function iniciarPantalla() {
  document.addEventListener('click', pedirPantallaCompleta, true);
}
