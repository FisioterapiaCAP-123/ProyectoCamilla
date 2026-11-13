/* Lleva el estado a la pantalla. Solo lee estado.js: nunca manda ordenes. */
import { CONFIG, SECCIONES, SUFIJO } from '../config.js';
import { control, estaMoviendo, panel, puedeMover } from '../estado.js';
import { porId } from '../utilidades.js';
import { pintarDibujo } from './dibujo.js';

const el = {
  vistaPanel:   porId('vistaPanel'),
  topeAltura:   porId('topeAltura'),
  estado:       porId('estado'),
  estadoTexto:  porId('estadoTexto'),
  cintaParo:    porId('cintaParo'),
  cintaHardware: porId('cintaHardware'),
  btnParo:      porId('btnParo'),
  txtParo:      porId('txtParo'),
  btnBloqueo:   porId('btnBloqueo'),
  txtBloqueo:   porId('txtBloqueo'),
  anuncio:      porId('anuncio'),
  paroFlotante: porId('btnParoFlotante'),
  txtFlotante:  porId('txtParoFlotante'),
  barra:        porId('controlBarra'),
  inicial:      porId('controlInicial'),
  rotulo:       porId('controlRotulo'),
  nombre:       porId('controlNombre'),
  acciones:     porId('controlAcciones')
};

function pintarRiel(seccion) {
  const c = CONFIG[seccion];
  const rango = c.max - c.min;
  const suf = SUFIJO[seccion];
  const pct = (panel.valor[seccion] - c.min) / rango * 100;
  const ref = (c.ref - c.min) / rango * 100;
  const relleno = porId('relleno' + suf);
  relleno.style.left  = Math.min(pct, ref) + '%';
  relleno.style.width = Math.abs(pct - ref) + '%';
  porId('aguja' + suf).style.left = pct + '%';
  const marca = porId('cero' + suf);
  if (!marca) return;
  if (c.ref > c.min && c.ref < c.max) {
    marca.classList.remove('d-none');
    marca.style.left = ref + '%';
  } else {
    marca.classList.add('d-none');
  }
}

/* Finales de carrera: lo unico que de verdad se sabe de la altura */
function pintarTopeAltura() {
  const c = CONFIG.altura;
  const altura = panel.valor.altura;
  if (c.sinTope) {
    el.topeAltura.classList.add('d-none');   // la estimacion no sabe donde esta el motor real
  } else if (altura >= c.max) {
    el.topeAltura.classList.remove('d-none');
    el.topeAltura.textContent = 'En el tope superior';
  } else if (altura <= c.min) {
    el.topeAltura.classList.remove('d-none');
    el.topeAltura.textContent = 'En el tope inferior';
  } else {
    el.topeAltura.classList.add('d-none');
  }
}

function pintarSeccion(seccion) {
  const suf = SUFIJO[seccion];
  const { manual, hardware } = panel;
  porId('tarjeta' + suf).classList.toggle('en-movimiento', estaMoviendo(seccion));
  porId('sinActuador' + suf).classList.toggle('d-none', !hardware.conectado || hardware.secciones.includes(seccion));
  if (seccion === 'altura') {
    pintarRiel(seccion);
    pintarTopeAltura();
    return;
  }
  /* Cabeza y piernas no tienen sensor: en lugar de grados se dice si esta subiendo o bajando */
  const dir = manual && manual.seccion === seccion ? manual.dir : 0;
  const caja = porId('mov' + suf);
  if (caja.dataset.dir !== String(dir)) {
    caja.dataset.dir = String(dir);
    porId('txtMov' + suf).textContent = dir > 0 ? 'Subiendo' : (dir < 0 ? 'Bajando' : 'En reposo');
  }
}

function pintarEstado() {
  const { paro, bloqueo, manual, destino } = panel;
  let tono = 'listo';
  let texto = 'Listo';
  if (paro)                    { tono = 'alerta';     texto = 'Paro de emergencia'; }
  else if (!control.conectado) { tono = 'alerta';     texto = 'Sin conexión'; }
  else if (!panel.hardware.conectado) { tono = 'alerta'; texto = 'Sin conexión con los motores'; }
  else if (bloqueo)            { tono = 'alerta';     texto = 'Controles bloqueados'; }
  else if (!control.soyYo)     { tono = 'listo';      texto = 'Solo lectura'; }
  else if (manual)             { tono = 'movimiento'; texto = CONFIG[manual.seccion].etiqueta + (manual.dir > 0 ? ' ↑ subiendo' : ' ↓ bajando'); }
  else if (destino)            { tono = 'movimiento'; texto = 'Ajustando a ' + destino.nombre; }
  if (el.estado.dataset.tono !== tono) el.estado.dataset.tono = tono;
  if (el.estadoTexto.textContent !== texto) el.estadoTexto.textContent = texto;
}

function pintarBotones() {
  const { paro, bloqueo, manual, valor } = panel;
  document.querySelectorAll('.btn-mover').forEach((boton) => {
    const seccion = boton.dataset.seccion;
    const dir = parseInt(boton.dataset.dir, 10);
    const c = CONFIG[seccion];
    const enLimite = !c.sinTope && (dir > 0 ? valor[seccion] >= c.max : valor[seccion] <= c.min);
    boton.disabled = !puedeMover(seccion) || enLimite;
    boton.classList.toggle('presionado', Boolean(manual && manual.seccion === seccion && manual.dir === dir));
  });
  /* Bloquear es una accion de quien opera; sin el control no tiene sentido.
     El PARO queda fuera de esta regla a proposito: nunca se deshabilita. */
  el.btnBloqueo.disabled = !control.soyYo || !control.conectado;
  el.btnParo.classList.toggle('btn-danger', !paro);
  el.btnParo.classList.toggle('btn-outline-danger', paro);
  el.txtParo.textContent = paro ? 'Liberar' : 'Paro';
  el.cintaParo.classList.toggle('d-none', !paro);
  el.cintaHardware.classList.toggle('d-none', panel.hardware.conectado);
  el.btnBloqueo.setAttribute('aria-pressed', bloqueo ? 'true' : 'false');
  el.btnBloqueo.classList.toggle('active', bloqueo);
  el.txtBloqueo.textContent = bloqueo ? 'Desbloquear' : 'Bloquear';
  pintarParoFlotante();
}

export function pintarParoFlotante() {
  const { paro, modalActivo, pestana } = panel;
  const visible = el.vistaPanel.hidden || Boolean(modalActivo) || pestana !== 'control';
  el.paroFlotante.classList.toggle('d-none', !visible);
  el.paroFlotante.classList.toggle('btn-danger', !paro);
  el.paroFlotante.classList.toggle('btn-light', paro);
  el.txtFlotante.textContent = paro ? 'Liberar paro' : 'Paro';
}

function botonControl(accion, tono, texto) {
  return `<button type="button" class="btn ${tono} tipo-titulo text-uppercase fw-semibold px-3 btn-barra" data-accion="${accion}">${texto}</button>`;
}

function datosBarraControl() {
  if (!control.conectado) {
    return { estado: 'sin-conexion', rotulo: 'Sin conexión', nombre: 'Movimiento inhibido', inicial: '!', acciones: '' };
  }
  if (!control.titular) {
    return { estado: 'libre', rotulo: 'Control de la camilla', nombre: 'No lo tiene nadie', inicial: '—',
             acciones: botonControl('tomar', 'btn-primary', 'Tomar el control') };
  }
  const inicial = control.titular.charAt(0).toUpperCase();
  if (control.soyYo) {
    return { estado: 'mio', rotulo: 'Tienes el control', nombre: control.titular, inicial,
             acciones: botonControl('liberar', 'btn-outline-secondary border-2', 'Liberar control') };
  }
  return { estado: 'ajeno', rotulo: 'Solo lectura', nombre: control.titular, inicial,
           acciones: botonControl('solicitar', 'btn-primary', 'Solicitar control') };
}

function pintarControl() {
  const datos = datosBarraControl();
  el.barra.dataset.estado = datos.estado;
  el.rotulo.textContent = datos.rotulo;
  el.nombre.textContent = datos.nombre;
  el.inicial.textContent = datos.inicial;
  if (el.acciones.dataset.estado !== datos.estado) {
    el.acciones.innerHTML = datos.acciones;
    el.acciones.dataset.estado = datos.estado;
  }
}

export function pintar() {
  pintarDibujo();
  SECCIONES.forEach(pintarSeccion);
  pintarEstado();
  pintarBotones();
  pintarControl();
}

/* Texto para lectores de pantalla */
export function anunciar() {
  const { valor } = panel;
  let altura = '';
  if (valor.altura >= CONFIG.altura.max) altura = ' Altura en el tope superior.';
  else if (valor.altura <= CONFIG.altura.min) altura = ' Altura en el tope inferior.';
  el.anuncio.textContent = `Movimiento detenido.${altura}`;
}
