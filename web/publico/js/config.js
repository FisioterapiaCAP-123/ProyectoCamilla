/* Parametros del panel. Los limites de angulo deben coincidir con
   LIMITES en web/servidor.py.

   ALTURA es distinta a las otras dos: no tiene sensor de posicion, asi que
   no se muestran centimetros. Solo se sabe si esta en un final de carrera.
   Su valor 0-100 es una estimacion interna que SOLO sirve para animar el
   dibujo y la barra; nunca se muestra como numero. */
export const CONFIG = {
  altura:  { min: 0, max: 100, ref: 0, paso: 2, numerica: false, continua: true,
             etiqueta: 'Altura' },
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

export const ROLES = { admin: 'Administrador', fisio: 'Fisioterapeuta' };

export const CONSULTA_MS = 1000;      // cada cuanto se pregunta el estado al servidor
export const FALLOS_PARA_CAIDA = 3;   // consultas fallidas seguidas antes de "Sin conexion"
export const MANTENER_MS = 400;       // un motor continuo se mantiene repitiendo "mover" (hombre muerto)
export const ESPERA_SOLICITUD = 30;   // segundos que espero una respuesta
export const ESPERA_RESPUESTA = 30;   // segundos que tengo para decidir
