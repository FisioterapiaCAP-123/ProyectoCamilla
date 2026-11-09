/* Pantalla de acceso: iniciar sesion y crear perfil. */
import { SERVIDOR } from '../api/ordenes.js';
import { AVISO_CARACTERES, marcarCampo, ocupado, revisarClave, SOLO_LETRAS, SOLO_LETRAS_NUMEROS } from '../ui/formularios.js';
import { porId } from '../utilidades.js';

const PAUSA_BIENVENIDA_MS = 650;
const SIN_CONEXION = 'No se pudo contactar con la camilla. Revisa la conexión.';

const formLogin = porId('formLogin');
const formRegistro = porId('formRegistro');
const alerta = porId('loginAlerta');
const btnIngresar = porId('btnIngresar');
const btnRegistrar = porId('btnRegistrar');
const campoUsuario = porId('loginUsuario');
const campoClave = porId('loginClave');
const REGISTRO = {
  nombre:  porId('regNombre'),
  usuario: porId('regUsuario'),
  clave:   porId('regClave'),
  clave2:  porId('regClave2')
};

let alEntrar = () => {};

export function avisoLogin(texto, tipo) {
  alerta.classList.remove('d-none', 'alert-danger', 'alert-success');
  alerta.classList.add(tipo === 'ok' ? 'alert-success' : 'alert-danger');
  alerta.textContent = texto;
}

/* Un solo cuadro: o se entra, o se crea el perfil */
function mostrarFormulario(cual) {
  const registro = cual === 'registro';
  formLogin.hidden = registro;
  formRegistro.hidden = !registro;
  porId('loginSubtitulo').textContent = registro ? 'Crear perfil nuevo' : 'Acceso al panel de operación';
  alerta.classList.add('d-none');
  (registro ? REGISTRO.nombre : campoUsuario).focus();
}

/* Deja la pantalla lista para la proxima vez que se muestre */
export function reiniciarAcceso() {
  campoClave.value = '';
  campoClave.classList.remove('is-invalid');
  mostrarFormulario('login');
}

/* Respuesta buena de /api/login o /api/registro: al panel */
function entrar(r) {
  avisoLogin('Acceso correcto. Abriendo el panel...', 'ok');
  setTimeout(() => alEntrar(r, r.control, r.sesion), PAUSA_BIENVENIDA_MS);
}

function alternarVerClave(e) {
  const boton = e.currentTarget;
  const mostrando = campoClave.type === 'text';
  campoClave.type = mostrando ? 'password' : 'text';
  boton.setAttribute('aria-pressed', mostrando ? 'false' : 'true');
  boton.setAttribute('aria-label', mostrando ? 'Mostrar la contraseña' : 'Ocultar la contraseña');
  campoClave.focus();
}

function iniciarSesion(e) {
  e.preventDefault();
  const usuario = campoUsuario.value.trim();
  const clave = campoClave.value;

  campoUsuario.classList.remove('is-invalid');
  campoClave.classList.remove('is-invalid');

  if (!usuario) return marcarCampo(campoUsuario, 'Escribe tu usuario.');
  if (!SOLO_LETRAS_NUMEROS.test(usuario)) return marcarCampo(campoUsuario, AVISO_CARACTERES);
  if (!clave) return marcarCampo(campoClave, 'Escribe tu contraseña.');
  if (!SOLO_LETRAS_NUMEROS.test(clave)) return marcarCampo(campoClave, AVISO_CARACTERES);

  alerta.classList.add('d-none');
  ocupado(btnIngresar, 'Entrando...');

  SERVIDOR.login(usuario, clave).then((r) => {
    ocupado(btnIngresar);
    if (!r || !r.ok) {
      avisoLogin((r && r.mensaje) || 'Usuario o contraseña incorrectos.', 'error');
      campoClave.value = '';
      campoClave.classList.add('is-invalid');
      campoClave.focus();
      return;
    }
    entrar(r);
  }).catch(() => {
    ocupado(btnIngresar);
    avisoLogin(SIN_CONEXION, 'error');
  });
}

function crearPerfil(e) {
  e.preventDefault();
  const nombre = REGISTRO.nombre.value.trim();
  const usuario = REGISTRO.usuario.value.trim().toLowerCase();
  Object.values(REGISTRO).forEach((campo) => campo.classList.remove('is-invalid'));

  if (!nombre) return marcarCampo(REGISTRO.nombre, 'Escribe tu nombre.');
  if (!SOLO_LETRAS.test(nombre)) return marcarCampo(REGISTRO.nombre, 'Solo letras, sin números, tildes, símbolos ni espacios.');
  if (nombre.length < 2) return marcarCampo(REGISTRO.nombre, 'El nombre debe tener al menos 2 letras.');
  if (!SOLO_LETRAS_NUMEROS.test(usuario)) return marcarCampo(REGISTRO.usuario, AVISO_CARACTERES);
  if (usuario.length < 3) return marcarCampo(REGISTRO.usuario, 'El usuario debe tener al menos 3 caracteres.');
  const errorClave = revisarClave(REGISTRO.clave.value);
  if (errorClave) return marcarCampo(REGISTRO.clave, errorClave);
  if (REGISTRO.clave.value !== REGISTRO.clave2.value) return marcarCampo(REGISTRO.clave2);

  alerta.classList.add('d-none');
  ocupado(btnRegistrar, 'Creando perfil...');

  SERVIDOR.registro(usuario, nombre, REGISTRO.clave.value).then((r) => {
    ocupado(btnRegistrar);
    if (!r || !r.ok) {
      if (r && REGISTRO[r.campo]) marcarCampo(REGISTRO[r.campo], r.mensaje);
      else avisoLogin((r && r.mensaje) || 'No se pudo crear el perfil.', 'error');
      return;
    }
    formRegistro.reset();
    entrar(r);
  }).catch(() => {
    ocupado(btnRegistrar);
    avisoLogin(SIN_CONEXION, 'error');
  });
}

/* alEntrar(perfil, control, token): lo llama cuando el servidor acepta a la persona */
export function iniciarAcceso(funcionEntrar) {
  alEntrar = funcionEntrar;
  btnIngresar.dataset.texto = 'Ingresar';
  btnRegistrar.dataset.texto = 'Crear perfil';
  porId('irRegistro').addEventListener('click', () => mostrarFormulario('registro'));
  porId('irLogin').addEventListener('click', () => mostrarFormulario('login'));
  porId('verClave').addEventListener('click', alternarVerClave);
  formLogin.addEventListener('submit', iniciarSesion);
  formRegistro.addEventListener('submit', crearPerfil);
}
