/* Reglas y ayudas de los formularios. Las reglas son las mismas de web/basedatos.py,
   que es quien de verdad las aplica. */
import { porId } from '../utilidades.js';

export const SOLO_LETRAS_NUMEROS = /^[A-Za-z0-9]+$/;   // sin tildes, ñ, simbolos ni espacios
export const SOLO_LETRAS = /^[A-Za-z]+$/;              // el nombre que ven los demas: ni numeros
export const AVISO_CARACTERES = 'Solo letras y números, sin tildes, símbolos ni espacios.';

const CLAVE_MINIMA = 6;

export function revisarClave(clave) {
  if (!SOLO_LETRAS_NUMEROS.test(clave)) return clave ? AVISO_CARACTERES : 'Escribe la contraseña.';
  if (clave.length < CLAVE_MINIMA) return 'La contraseña debe tener al menos 6 caracteres.';
  return null;
}

/* El aviso de cada campo tiene el id del campo terminado en "Aviso" */
export function marcarCampo(campo, texto) {
  const aviso = porId(campo.id + 'Aviso');
  if (aviso && texto) aviso.textContent = texto;
  campo.classList.add('is-invalid');
  campo.focus();
}

/* Boton con spinner mientras se espera; sin texto vuelve a su rotulo (data-texto) */
export function ocupado(boton, texto) {
  boton.disabled = Boolean(texto);
  boton.innerHTML = '';
  if (texto) boton.insertAdjacentHTML('beforeend', '<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>');
  boton.appendChild(document.createTextNode(texto || boton.dataset.texto));
}
