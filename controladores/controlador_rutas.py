from bd_conexion import obtener_conexion

def registrar_ruta_y_asignacion(id_persona, id_vehiculo, destino_lat, destino_lon, destino, fecha):
    conexion = obtener_conexion()
    try:
        if not destino_lat or not destino_lon or not destino:
            return False, "Faltan campos requeridos", None

        with conexion.cursor() as cursor:
            # Validar si ya existe una ruta para ese conductor en esa fecha
            cursor.execute("""
                SELECT 1
                FROM rutas_programadas rp
                JOIN asignacion_ruta_conductor arc ON rp.id = arc.id_ruta
                WHERE arc.id_persona = %s AND rp.fecha = %s;
            """, (id_persona, fecha))
            
            if cursor.fetchone():
                return False, "El conductor ya tiene una ruta asignada en esta fecha.", None

            # Insertar nueva ruta
            cursor.execute("""
                INSERT INTO rutas_programadas (
                    destino, destino_lat, destino_lon, fecha
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id;
            """, (destino, destino_lat, destino_lon, fecha))
            
            id_ruta = cursor.fetchone()[0]

            # Asignar ruta a conductor y vehículo
            cursor.execute("""
                INSERT INTO asignacion_ruta_conductor (id_persona, id_vehiculo, id_ruta)
                VALUES (%s, %s, %s);
            """, (id_persona, id_vehiculo, id_ruta))

            # Cambiar estado del vehículo
            cursor.execute("UPDATE vehiculos SET estado = FALSE WHERE id = %s;", (id_vehiculo,))

        conexion.commit()
        return True, "Ruta registrada correctamente", id_ruta
    except Exception as e:
        conexion.rollback()
        return False, str(e), None
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
                    "id_persona": row[10],   # 👈 ahora disponibles
                    "id_vehiculo": row[11],  # 👈 ahora disponibles
                    "conductor": row[12],
                    "vehiculo": row[13],
                    "duracion": calcular_duracion(row[8], row[9]) if row[9] else None
                })
    except Exception as e:
        print("Error al obtener rutas programadas:", e)
    finally:
        conexion.close()

    return rutas


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
