/* Pedidos de administracion: el servidor solo los acepta con rol admin. */
import { llamar } from './cliente.js';

export const ADMIN = {
  // POST /api/pacientes/lista            -> {ok, pacientes:[{id, nombre, edad, creado, creado_por}]}
  pacientes() { return llamar('/api/pacientes/lista'); },
  // POST /api/pacientes/guardar {id|null, nombre, edad}   id null = registro nuevo
  guardarPaciente(paciente) { return llamar('/api/pacientes/guardar', paciente); },
  // POST /api/pacientes/borrar {id}
  borrarPaciente(id) { return llamar('/api/pacientes/borrar', { id }); },
  // POST /api/usuarios/lista             -> {ok, usuarios:[{id, usuario, nombre, rol, activo, creado}]}
  usuarios() { return llamar('/api/usuarios/lista'); },
  // POST /api/usuarios/{rol|activo|clave|borrar} {id, rol|activo|clave}   nunca el perfil propio
  cambiarUsuario(accion, datos) { return llamar('/api/usuarios/' + accion, datos); }
};
