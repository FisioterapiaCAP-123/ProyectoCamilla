/* Boton "Manuales" del encabezado: baja el manual de usuario (todos) o el tecnico (solo administrador).
   Los PDF estan en web/manuales/ y los entrega POST /api/manual con la sesion. */
import { descargar } from '../api/cliente.js';
import { esAdmin } from '../config.js';
import { sesion } from '../estado.js';
import { mostrarAviso, revisar } from '../ui/avisos.js';
import { abrirModal, cerrarModal } from '../ui/modales.js';
import { bajarArchivo, porId } from '../utilidades.js';

const NOMBRES = { usuario: 'Manual de usuario', tecnico: 'Manual técnico' };

function abrirManuales() {
  porId('manualTecnico').hidden = !esAdmin(sesion.rol);   // el servidor tambien lo revisa
  abrirModal('modalManuales');
}

function bajarManual(boton) {
  const tipo = boton.dataset.manual;
  boton.disabled = true;
  descargar('/api/manual', { tipo }).then((r) => {
    if (!revisar(r)) return;
    bajarArchivo(r.archivo, r.nombre);
    mostrarAviso(`${NOMBRES[tipo]} descargado`, 'ok');
  }, () => revisar(null)).finally(() => { boton.disabled = false; });
}

export function iniciarManuales() {
  porId('btnManuales').addEventListener('click', abrirManuales);
  porId('btnManualesCerrar').addEventListener('click', cerrarModal);
  porId('modalManuales').addEventListener('click', (e) => {
    const boton = e.target.closest('[data-manual]');
    if (boton) bajarManual(boton);
  });
}
