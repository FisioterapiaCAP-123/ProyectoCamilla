/* Pedidos de administracion: el servidor solo los acepta con rol admin. */
import { llamar } from './cliente.js';

export const ADMIN = {
  // POST /api/pacientes/lista            -> {ok, pacientes:[{id, ...campos, creado, creado_por}]}
  //   campos (todos opcionales, null si vacio): nombres, apellidos, sexo, nacimiento, dpi, carne, telefono,
  //   correo, emergencia_nombre, emergencia_telefono, estatura (m), peso (lb), fisioterapeuta, diagnostico,
  //   dolor (0-10), proxima_cita ("AAAA-MM-DD HH:MM", 24 h), notas
  pacientes() { return llamar('/api/pacientes/lista'); },
  // POST /api/pacientes/guardar {id|null, ...campos}   id null = registro nuevo
  guardarPaciente(paciente) { return llamar('/api/pacientes/guardar', paciente); },
  // POST /api/pacientes/borrar {id}
  borrarPaciente(id) { return llamar('/api/pacientes/borrar', { id }); },
  // POST /api/usuarios/lista             -> {ok, usuarios:[{id, usuario, nombre, rol, activo, creado}]}
  usuarios() { return llamar('/api/usuarios/lista'); },
  // POST /api/usuarios/{rol|activo|clave|borrar} {id, rol|activo|clave}   nunca el perfil propio
  cambiarUsuario(accion, datos) { return llamar('/api/usuarios/' + accion, datos); }
};
