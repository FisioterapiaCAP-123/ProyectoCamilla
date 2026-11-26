/* Lleva el estado a la pantalla. Solo lee estado.js: nunca manda ordenes. */
import { CONFIG, SECCIONES, SECCIONES_NUMERICAS, SUFIJO } from '../config.js';
import { bloqueoAltura, conSensor, control, estaMoviendo, panel, puedeMover, sesion } from '../estado.js';
import { conSigno, porId } from '../utilidades.js';
import { pintarDibujo } from './dibujo.js';

const el = {
  vistaPanel:   porId('vistaPanel'),
  estado:       porId('estado'),
  estadoTexto:  porId('estadoTexto'),
  cintaParo:    porId('cintaParo'),
  cintaHardware: porId('cintaHardware'),
  btnParo:      porId('btnParo'),
  txtParo:      porId('txtParo'),
  btnPlano:     porId('btnPlano'),
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
  const pct = (Math.min(c.max, Math.max(c.min, panel.valor[seccion])) - c.min) / rango * 100;
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

function pintarSeccion(seccion) {
  const suf = SUFIJO[seccion];
  const { destino, valor, hardware } = panel;
  pintarRiel(seccion);
  porId('tarjeta' + suf).classList.toggle('en-movimiento', estaMoviendo(seccion));
  porId('sinActuador' + suf).classList.toggle('d-none', !hardware.conectado || hardware.secciones.includes(seccion));
  if (seccion === 'altura') {   // sin numero que mostrar: su modo y, para el desarrollador, sus pasos
    pintarAltura();
    return;
  }
  porId('val' + suf).textContent = conSigno(valor[seccion]);
  porId('obj' + suf).textContent = (destino && destino[seccion] !== null) ? conSigno(destino[seccion]) + '°' : '—';
  pintarSensor(seccion);
}

/* De donde sale el angulo, y el panel de calibrar (solo el perfil Desarrollador) */
const SENSOR = {
  ok:     ['Sensor', 'text-bg-success'],
  sincal: ['Sin calibrar', 'text-bg-warning'],
  plano:  ['Falta subido', 'text-bg-warning'],
  poco:   ['Calibrar de nuevo', 'text-bg-warning'],
  falla:  ['Falla del sensor', 'text-bg-danger']
};
const PASO_CALIBRAR = {
  sincal: 'Sin calibrar. Paso 1: la sección en plano y Guardar plano.',
  plano:  'Plano guardado. Paso 2: sube la sección unos 30° y toca Guardar subido.',
  poco:   'Quedó muy cerca de plano: sube más (al menos 15°) y toca Guardar subido otra vez.',
  falla:  'El sensor no responde: revisa sus cables. Mientras tanto el ángulo es estimado.'
};

function pintarSensor(seccion) {
  const suf = SUFIJO[seccion];
  const sensor = panel.sensores[seccion];
  const [texto, tono] = sensor ? SENSOR[sensor.estado] || SENSOR.falla : ['Estimado', 'text-bg-light'];
  const badge = porId('sensor' + suf);
  if (badge.textContent !== texto) badge.textContent = texto;
  badge.className = 'badge tipo-dato text-uppercase ms-auto ' + tono;

  const puede = sesion.rol === 'dev' && Boolean(sensor);
  if (!puede && panel.calibrando === seccion) panel.calibrando = null;
  porId('btnCalibrar' + suf).classList.toggle('d-none', !puede || panel.calibrando === seccion);
  const caja = porId('calibrar' + suf);
  caja.classList.toggle('d-none', panel.calibrando !== seccion);
  if (panel.calibrando !== seccion) return;
  const estado = sensor.estado;
  porId('calEstado' + suf).textContent = estado === 'ok'
    ? `Calibrado: ahora marca ${conSigno(Math.round(sensor.angulo))}°. Compruébalo con el nivel del celular.`
    : PASO_CALIBRAR[estado] || PASO_CALIBRAR.falla;
  const quieta = !estaMoviendo(seccion);
  const listo = control.conectado && panel.hardware.conectado && estado !== 'falla' && quieta;
  caja.querySelector('[data-posicion="plano"]').disabled = !listo;
  caja.querySelector('[data-posicion="subido"]').disabled = !listo || estado === 'sincal';
}

/* Altura: automatico o manual (pedal), su aviso y el panel de pasos (solo el perfil Desarrollador) */
const AVISO_ALTURA = {
  manual:       ['alert-warning', 'Manual: la altura se mueve con el pedal de la camilla. Sus botones están bloqueados.'],
  sincentro:    ['alert-warning', 'Falta poner el centro de la altura: queda bloqueada hasta que el perfil Desarrollador lo ponga.'],
  sincentroDev: ['alert-info', 'Sin centro: la cuenta de pasos no vale y la altura va despacio. Llévala al centro y toca «Aquí es el centro» en Pasos.']
};

function textoPasos(a) {
  if (a.modo === 'manual') return 'En manual la cuenta no vale: pasa a Automático para calibrar.';
  if (!a.centro) return 'Paso 1: lleva la altura al centro y toca Aquí es el centro.';
  if (a.topes.arriba === null) return 'Centro puesto. Paso 2: sube hasta casi el final y toca Guardar tope de arriba.';
  if (a.topes.abajo === null) return 'Paso 3: baja hasta casi el final y toca Guardar tope de abajo.';
  return `Calibrada: ${a.topes.arriba - a.topes.abajo} pasos de recorrido. La altura frena cerca de cada tope y se detiene sola.`;
}

function pintarAltura() {
  const a = panel.altura;
  const dev = sesion.rol === 'dev' && Boolean(a);
  const enLinea = control.conectado && panel.hardware.conectado;
  const badge = porId('modoAltura');
  badge.classList.toggle('d-none', !a);
  if (a) {
    const manual = a.modo === 'manual';
    badge.textContent = manual ? 'Manual · pedal' : 'Automático';
    badge.className = 'badge tipo-dato text-uppercase ms-auto ' + (manual ? 'text-bg-warning' : 'text-bg-success');
  }
  porId('filaModoAltura').classList.toggle('d-none', !dev);
  if (dev) {
    ['Auto', 'Manual'].forEach((m) => {
      const radio = porId('modoAltura' + m);
      radio.checked = a.modo === m.toLowerCase();
      radio.disabled = !enLinea;
    });
  }

  const hayTopes = Boolean(a) && (a.topes.abajo !== null || a.topes.arriba !== null);
  const clave = bloqueoAltura() || (dev && a.modo === 'auto' && hayTopes && !a.centro ? 'sincentroDev' : '');
  const aviso = porId('avisoAltura');
  aviso.classList.toggle('d-none', !clave);
  if (clave) {
    aviso.className = 'alert py-2 px-3 mb-0 small ' + AVISO_ALTURA[clave][0];
    if (aviso.textContent !== AVISO_ALTURA[clave][1]) aviso.textContent = AVISO_ALTURA[clave][1];
  }
  porId('textoAltura').textContent = 'Mantén presionado hasta alcanzar la altura deseada. ' +
    (conSensor('altura') ? 'La barra muestra la posición real, entre los topes.' : 'El recorrido es aproximado.');

  if (!dev && panel.pasosAbiertos) panel.pasosAbiertos = false;
  porId('btnPasosAltura').classList.toggle('d-none', !dev || panel.pasosAbiertos);
  const caja = porId('pasosAltura');
  caja.classList.toggle('d-none', !panel.pasosAbiertos);
  if (!panel.pasosAbiertos) return;

  const { pasos, centro, topes, modo } = a;
  porId('numPasosAltura').textContent = conSigno(pasos);
  porId('centroAltura').textContent = modo === 'manual' ? 'no vale (manual)' : (centro ? 'puesto' : 'falta');
  const lo = topes.abajo !== null ? topes.abajo : Math.min(-1000, pasos - 500);
  const hi = topes.arriba !== null ? topes.arriba : Math.max(1000, pasos + 500);
  const pct = (v) => Math.max(0, Math.min(100, (v - lo) / (hi - lo) * 100));
  porId('pasosAguja').style.left = pct(pasos) + '%';
  porId('pasosCero').style.left = pct(0) + '%';
  const relleno = porId('pasosRelleno');
  relleno.style.left = Math.min(pct(0), pct(pasos)) + '%';
  relleno.style.width = Math.abs(pct(pasos) - pct(0)) + '%';
  porId('pasosMin').textContent = topes.abajo !== null ? 'tope ' + topes.abajo : 'sin tope abajo';
  porId('pasosMax').textContent = topes.arriba !== null ? 'tope +' + topes.arriba : 'sin tope arriba';

  const listo = enLinea && !estaMoviendo('altura') && modo === 'auto';
  caja.querySelector('[data-altura="centro"]').disabled = !listo;
  caja.querySelector('[data-altura="arriba"]').disabled = !listo || !centro || pasos < 1;
  caja.querySelector('[data-altura="abajo"]').disabled = !listo || !centro || pasos > -1;
  caja.querySelector('[data-altura="borrar"]').disabled = !listo || !hayTopes;
  porId('pasosEstado').textContent = textoPasos(a);
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
  const habilitado = puedeMover();
  document.querySelectorAll('.btn-mover').forEach((boton) => {
    const seccion = boton.dataset.seccion;
    const dir = parseInt(boton.dataset.dir, 10);
    const c = CONFIG[seccion];
    const enLimite = !c.sinTope && (dir > 0 ? valor[seccion] >= c.max : valor[seccion] <= c.min);
    boton.disabled = !puedeMover(seccion) || enLimite;
    boton.classList.toggle('presionado', Boolean(manual && manual.seccion === seccion && manual.dir === dir));
  });
  SECCIONES_NUMERICAS.forEach((seccion) => {
    /* "Ir a" no mueve motores: con sensor real no se ofrece */
    porId('ir' + SUFIJO[seccion]).disabled = !puedeMover(seccion) || conSensor(seccion);
    porId('campo' + SUFIJO[seccion]).disabled = !puedeMover(seccion) || conSensor(seccion);
  });
  el.btnPlano.disabled = !habilitado;
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
    return { estado: 'sin-conexion', rotulo: 'Sin conexión', nombre: 'Movimiento deshabilitado', inicial: '!', acciones: '' };
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
  el.anuncio.textContent = `Cabeza ${valor.cabeza} grados, piernas ${valor.piernas} grados.${altura}`;
}

/* Rotulos fijos de los rieles: minimo, maximo y referencia */
export function prepararEscalas() {
  SECCIONES_NUMERICAS.forEach((seccion) => {
    const c = CONFIG[seccion];
    const suf = SUFIJO[seccion];
    porId('min' + suf).textContent = conSigno(c.min) + '°';
    porId('max' + suf).textContent = conSigno(c.max) + '°';
    const referencia = porId('etqCero' + suf);
    if (c.ref > c.min && c.ref < c.max) {
      referencia.classList.remove('d-none');
      referencia.textContent = conSigno(c.ref) + '°';
      referencia.style.left = ((c.ref - c.min) / (c.max - c.min) * 100) + '%';
    } else {
      referencia.classList.add('d-none');
    }
  });
}
