/* Parametros del panel. Los limites de angulo son los del dibujo y del riel; con sensor
   (MPU6050) el numero muestra el angulo real aunque se salga de ellos.

   ALTURA es distinta a las otras dos: no tiene sensor de posicion ni finales
   de carrera, asi que no se muestran centimetros.
   Su valor 0-100 es una estimacion interna que SOLO sirve para animar el
   dibujo y la barra; nunca se muestra como numero. */
export const CONFIG = {
  altura:  { min: 0, max: 100, ref: 0, paso: 2, numerica: false, continua: true,
             sinTope: true, etiqueta: 'Altura' },
  /* continua: el motor corre mientras se mantiene el boton. sinTope: su final de
     recorrido no lo decide la estimacion de la pagina. */
  cabeza:  { min: -30, max: 70, ref: 0, paso: 1, numerica: true, unidad: '°',
             continua: true, sinTope: true, etiqueta: 'Cabeza' },
  piernas: { min: 0, max: 45, ref: 0, paso: 1, numerica: true, unidad: '°',
             continua: true, sinTope: true, etiqueta: 'Piernas' }
};

export const RITMO = {
  esperaRepeticion: 450,  // ms que hay que mantener pulsado antes de repetir
  repeticion:       160,  // ms entre paso y paso mientras se mantiene
  repeticionAltura:  70,  // la altura corre mas fluida porque solo anima el dibujo
  automatico:        90   // ms entre paso y paso al usar "Ir a" o "Plano"
};

export const SECCIONES = ['altura', 'cabeza', 'piernas'];
export const SECCIONES_NUMERICAS = SECCIONES.filter((s) => CONFIG[s].numerica);

/* Sufijo de los id del HTML: valCabeza, rellenoPiernas, tarjetaAltura... */
export const SUFIJO = { altura: 'Altura', cabeza: 'Cabeza', piernas: 'Piernas' };

export const ROLES = { admin: 'Administrador', fisio: 'Fisioterapeuta', dev: 'Desarrollador' };
/* Desarrollador = administrador + depuracion + calibrar sensores. Solo se da desde la terminal. */
export const esAdmin = (rol) => rol === 'admin' || rol === 'dev';

export const CONSULTA_MS = 300;       // cada cuanto se pregunta el estado al servidor (trae el angulo de los sensores)
export const FALLOS_PARA_CAIDA = 3;   // consultas fallidas seguidas antes de "Sin conexion"
export const MANTENER_MS = 400;       // un motor continuo se mantiene repitiendo "mover" (hombre muerto)
export const ESPERA_SOLICITUD = 30;   // segundos que espero una respuesta
export const ESPERA_RESPUESTA = 30;   // segundos que tengo para decidir
