from bd_conexion import obtener_conexion
from datetime import date

def registrar_ruta_solo_con_vehiculo(id_vehiculo, destino_lat, destino_lon, destino, fecha):
    conexion = obtener_conexion()
    try:
        if not destino_lat or not destino_lon or not destino or not id_vehiculo or not fecha:
            return False, "Faltan campos requeridos", None

        with conexion.cursor() as cursor:
            # Insertar nueva ruta
            cursor.execute("""
                INSERT INTO rutas_programadas (
                    destino, destino_lat, destino_lon, fecha
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id;
            """, (destino, destino_lat, destino_lon, fecha))

            id_ruta = cursor.fetchone()[0]

            # Asignar vehículo a ruta (sin conductor por ahora)
            cursor.execute("""
                INSERT INTO asignacion_ruta_conductor (id_ruta, id_vehiculo)
                VALUES (%s, %s);
            """, (id_ruta, id_vehiculo))

            # Cambiar estado del vehículo a ocupado
            cursor.execute("UPDATE vehiculos SET estado = FALSE WHERE id = %s;", (id_vehiculo,))

        conexion.commit()
        return True, "Ruta registrada correctamente", id_ruta
    except Exception as e:
        conexion.rollback()
        return False, str(e), None
    finally:
        conexion.close()
        
def asignar_conductor_a_ruta(id_ruta, id_persona):
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            # Verificar si la ruta ya tiene conductor
            cursor.execute("""
                SELECT id_persona FROM asignacion_ruta_conductor WHERE id_ruta = %s
            """, (id_ruta,))
            resultado = cursor.fetchone()
            if resultado and resultado[0]:
                return False, "La ruta ya tiene un conductor asignado."

            # Asignar conductor
            cursor.execute("""
                UPDATE asignacion_ruta_conductor
                SET id_persona = %s
                WHERE id_ruta = %s
            """, (id_persona, id_ruta))

        conexion.commit()
        return True, "Conductor asignado correctamente"
    except Exception as e:
        conexion.rollback()
        return False, str(e)
    finally:
        conexion.close()

def editar_ruta_programada(id_ruta, id_vehiculo, destino_lat, destino_lon, destino, fecha):
    conexion = obtener_conexion()
    try:
        if not destino_lat or not destino_lon or not destino or not id_vehiculo or not fecha or not id_ruta:
            return False, "Faltan campos requeridos"

        with conexion.cursor() as cursor:
            # Obtener vehículo actual asignado
            cursor.execute("""
                SELECT id_vehiculo FROM asignacion_ruta_conductor WHERE id_ruta = %s;
            """, (id_ruta,))
            vehiculo_actual = cursor.fetchone()
            vehiculo_actual = vehiculo_actual[0] if vehiculo_actual else None

            # ✅ Siempre actualiza datos de la ruta
            cursor.execute("""
                UPDATE rutas_programadas
                SET destino = %s, destino_lat = %s, destino_lon = %s, fecha = %s
                WHERE id = %s;
            """, (destino, destino_lat, destino_lon, fecha, id_ruta))

            # ✅ Solo actualiza asignación de vehículo si cambia
            if vehiculo_actual != int(id_vehiculo):
                cursor.execute("""
                    UPDATE asignacion_ruta_conductor
                    SET id_vehiculo = %s
                    WHERE id_ruta = %s;
                """, (id_vehiculo, id_ruta))

                # Cambiar estado de vehículos
                if vehiculo_actual:
                    cursor.execute("UPDATE vehiculos SET estado = TRUE WHERE id = %s;", (vehiculo_actual,))
                cursor.execute("UPDATE vehiculos SET estado = FALSE WHERE id = %s;", (id_vehiculo,))

        conexion.commit()
        return True, "Ruta actualizada correctamente"
    except Exception as e:
        conexion.rollback()
        return False, f"Error en SQL: {str(e)}"
    finally:
        conexion.close()




def editar_conductor_de_ruta(id_ruta, nuevo_id_persona):
    conexion = obtener_conexion()
    try:
        if not id_ruta or not nuevo_id_persona:
            return False, "Faltan campos requeridos"

        with conexion.cursor() as cursor:
            # Obtener conductor anterior
            cursor.execute("""
                SELECT id_persona FROM asignacion_ruta_conductor WHERE id_ruta = %s;
            """, (id_ruta,))
            anterior = cursor.fetchone()
            id_anterior = anterior[0] if anterior else None

            # Actualizar al nuevo conductor
            cursor.execute("""
                UPDATE asignacion_ruta_conductor
                SET id_persona = %s
                WHERE id_ruta = %s;
            """, (nuevo_id_persona, id_ruta))

        conexion.commit()
        return True, "Conductor actualizado correctamente"
    except Exception as e:
        conexion.rollback()
        return False, str(e)
    finally:
        conexion.close()



def obtener_todos_los_conductores():
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT id, nombre, apellido
                FROM personas
                WHERE id_rol = (SELECT id FROM roles WHERE nombre = 'Conductor')
                ORDER BY apellido, nombre
            """)
            return [{"id": c[0], "nombre": c[1], "apellido": c[2]} for c in cursor.fetchall()]
    except Exception as e:
        print("Error al obtener conductores:", e)
        return []
    finally:
        conexion.close()

def obtener_vehiculos_disponibles(id_vehiculo_asignado=None):
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            if id_vehiculo_asignado:
                cursor.execute("""
                    SELECT id, modelo, placa
                    FROM vehiculos
                    WHERE estado = TRUE OR id = %s
                    ORDER BY modelo;
                """, (id_vehiculo_asignado,))
            else:
                cursor.execute("""
                    SELECT id, modelo, placa
                    FROM vehiculos
                    WHERE estado = TRUE
                    ORDER BY modelo;
                """)
            return [{"id": v[0], "modelo": v[1], "placa": v[2]} for v in cursor.fetchall()]
    except Exception as e:
        print("Error al obtener vehículos:", e)
        return []
    finally:
        conexion.close()
        
def obtener_vehiculo_por_id(id_vehiculo):
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT id, modelo, placa
                FROM vehiculos
                WHERE id = %s
            """, (id_vehiculo,))
            fila = cursor.fetchone()
            if fila:
                return {"id": fila[0], "modelo": fila[1], "placa": fila[2]}
            return None
    except Exception as e:
        print("Error al obtener vehículo:", e)
        return None
    finally:
        conexion.close()

def obtener_todos_los_vehiculos_con_estado():
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT id, modelo, placa, estado
                FROM vehiculos
                ORDER BY modelo
            """)
            return [{"id": v[0], "modelo": v[1], "placa": v[2], "estado": v[3]} for v in cursor.fetchall()]
    except Exception as e:
        print("Error al obtener vehículos:", e)
        return []
    finally:
        conexion.close()



def obtener_rutas_programadas():
    conexion = obtener_conexion()
    rutas = []

    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    rp.id,
                    rp.origen,
                    rp.origen_lat,
                    rp.origen_lon,
                    rp.destino,
                    rp.destino_lat,
                    rp.destino_lon,
                    rp.fecha,
                    rp.hora_salida,
                    rp.hora_llegada,
                    arc.id_persona,
                    arc.id_vehiculo,
                    CONCAT(COALESCE(p.nombre, ''), ' ', COALESCE(p.apellido, '')) AS conductor,
                    CONCAT(v.modelo, ' - ', v.placa) AS vehiculo
                FROM rutas_programadas rp
                JOIN asignacion_ruta_conductor arc ON rp.id = arc.id_ruta
                LEFT JOIN personas p ON arc.id_persona = p.id
                JOIN vehiculos v ON arc.id_vehiculo = v.id
                ORDER BY rp.fecha ASC;
            """)

            for row in cursor.fetchall():
                rutas.append({
                    "id": row[0],
                    "origen": row[1],
                    "origen_lat": row[2],
                    "origen_lon": row[3],
                    "destino": row[4],
                    "destino_lat": row[5],
                    "destino_lon": row[6],
                    "fecha": row[7],
                    "hora_salida": row[8],
                    "hora_llegada": row[9],
                    "id_persona": row[10],
                    "id_vehiculo": row[11],
                    "conductor": row[12].strip() if row[12] else "Sin asignar",
                    "vehiculo": row[13],
                    "duracion": calcular_duracion(row[8], row[9]) if row[9] else None
                })
    except Exception as e:
        print("Error al obtener rutas programadas:", e)
    finally:
        conexion.close()

    return rutas

def obtener_rutas_sin_conductor():
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT rp.id, rp.destino, rp.fecha
                FROM rutas_programadas rp
                LEFT JOIN asignacion_ruta_conductor arc ON rp.id = arc.id_ruta
                WHERE arc.id_persona IS NULL
                  AND rp.fecha >= %s
                ORDER BY rp.fecha ASC;
            """, (date.today(),))
            columnas = [desc[0] for desc in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    except Exception as e:
        print("Error al obtener rutas sin conductor:", e)
        return []
    finally:
        conexion.close()

def obtener_conductores_asignados():
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    rp.id,                         -- ID de la ruta
                    arc.id_persona,                -- ID del conductor
                    arc.id_vehiculo,               -- ID del vehículo
                    CONCAT(p.nombre, ' ', p.apellido) AS conductor,
                    rp.destino,
                    rp.destino_lat,
                    rp.destino_lon,
                    rp.fecha
                FROM asignacion_ruta_conductor arc
                JOIN personas p ON arc.id_persona = p.id
                JOIN rutas_programadas rp ON arc.id_ruta = rp.id
                WHERE arc.id_persona IS NOT NULL
                ORDER BY rp.fecha DESC;
            """)
            columnas = [desc[0] for desc in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    except Exception as e:
        print("Error al obtener conductores asignados:", e)
        return []
    finally:
        conexion.close()




def obtener_rutas_con_estado_envio():
    conexion = obtener_conexion()
    rutas = []

    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    rp.id,
                    rp.origen,
                    rp.origen_lat,
                    rp.origen_lon,
                    rp.destino,
                    rp.destino_lat,
                    rp.destino_lon,
                    rp.fecha,
                    rp.hora_salida,
                    rp.hora_llegada,
                    rp.estado_envio,  -- ✅ campo necesario
                    arc.id_persona,
                    arc.id_vehiculo,
                    CONCAT(p.nombre, ' ', p.apellido) AS conductor,
                    CONCAT(v.modelo, ' - ', v.placa) AS vehiculo
                FROM rutas_programadas rp
                JOIN asignacion_ruta_conductor arc ON rp.id = arc.id_ruta
                JOIN personas p ON arc.id_persona = p.id
                JOIN vehiculos v ON arc.id_vehiculo = v.id
                ORDER BY rp.creado_en ASC;
            """)

            for row in cursor.fetchall():
                rutas.append({
                    "id": row[0],
                    "origen": row[1],
                    "origen_lat": row[2],
                    "origen_lon": row[3],
                    "destino": row[4],
                    "destino_lat": row[5],
                    "destino_lon": row[6],
                    "fecha": row[7],
                    "hora_salida": row[8],
                    "hora_llegada": row[9],
                    "estado_envio": row[10],           # ✅ nuevo
                    "id_persona": row[11],
                    "id_vehiculo": row[12],
                    "conductor": row[13],
                    "vehiculo": row[14],
                    "duracion": calcular_duracion(row[8], row[9]) if row[9] else None
                })
    except Exception as e:
        print("Error al obtener rutas con estado_envio:", e)
    finally:
        conexion.close()

    return rutas


def calcular_duracion(hora_salida, hora_llegada):
    try:
        from datetime import datetime, timedelta
        fmt = "%H:%M:%S"
        t1 = datetime.strptime(str(hora_salida), fmt)
        t2 = datetime.strptime(str(hora_llegada), fmt)
        if t2 < t1:
            t2 += timedelta(days=1)
        duracion = t2 - t1
        horas, resto = divmod(duracion.seconds, 3600)
        minutos = resto // 60
        return f"{horas}h {minutos}m"
    except:
        return "-"
    
def eliminar_ruta(id_ruta):
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            # Primero se obtiene el vehículo asignado para liberarlo
            cursor.execute("""
                SELECT id_vehiculo FROM asignacion_ruta_conductor
                WHERE id_ruta = %s
            """, (id_ruta,))
            vehiculo = cursor.fetchone()
            if vehiculo:
                id_vehiculo = vehiculo[0]
                # Liberar vehículo (volver a estado disponible)
                cursor.execute("""
                    UPDATE vehiculos SET estado = TRUE WHERE id = %s
                """, (id_vehiculo,))

            # Eliminar asignación
            cursor.execute("DELETE FROM asignacion_ruta_conductor WHERE id_ruta = %s", (id_ruta,))
            # Eliminar ruta
            cursor.execute("DELETE FROM rutas_programadas WHERE id = %s", (id_ruta,))
        
        conexion.commit()
        return True, "Ruta eliminada correctamente"
    except Exception as e:
        conexion.rollback()
        return False, str(e)
    finally:
        conexion.close()


def editar_ruta(id_ruta, id_persona, id_vehiculo, destino_lat, destino_lon, destino, fecha):
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            # Actualizar tabla rutas_programadas
            cursor.execute("""
                UPDATE rutas_programadas
                SET destino = %s,
                    destino_lat = %s,
                    destino_lon = %s,
                    fecha = %s
                WHERE id = %s;
            """, (destino, destino_lat, destino_lon, fecha, id_ruta))

            # Obtener el vehículo anterior
            cursor.execute("SELECT id_vehiculo FROM asignacion_ruta_conductor WHERE id_ruta = %s", (id_ruta,))
            vehiculo_anterior = cursor.fetchone()
            if vehiculo_anterior:
                cursor.execute("UPDATE vehiculos SET estado = TRUE WHERE id = %s", (vehiculo_anterior[0],))

            # Actualizar asignación (persona y vehículo)
            cursor.execute("""
                UPDATE asignacion_ruta_conductor
                SET id_persona = %s,
                    id_vehiculo = %s
                WHERE id_ruta = %s;
            """, (id_persona, id_vehiculo, id_ruta))

            # Marcar el nuevo vehículo como ocupado
            cursor.execute("UPDATE vehiculos SET estado = FALSE WHERE id = %s", (id_vehiculo,))
        
        conexion.commit()
        return True, "Ruta actualizada correctamente"
    except Exception as e:
        conexion.rollback()
        return False, str(e)
    finally:
        conexion.close()


