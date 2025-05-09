from bd_conexion import obtener_conexion

def registrar_ruta_y_asignacion(id_persona, id_vehiculo, destino_lat, destino_lon, destino, fecha, hora_salida):
    conexion = obtener_conexion()
    try:
        if not destino_lat or not destino_lon or not destino:
            return False, "Faltan campos requeridos", None

        with conexion.cursor() as cursor:
            cursor.execute("""
                INSERT INTO rutas_programadas (
                    destino, destino_lat, destino_lon,
                    fecha, hora_salida
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
            """, (destino, destino_lat, destino_lon, fecha, hora_salida))
            
            id_ruta = cursor.fetchone()[0]

            cursor.execute("""
                INSERT INTO asignacion_ruta_conductor (id_persona, id_vehiculo, id_ruta)
                VALUES (%s, %s, %s);
            """, (id_persona, id_vehiculo, id_ruta))

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

def obtener_vehiculos_disponibles():
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT id, modelo, placa
                FROM vehiculos
                WHERE estado = TRUE
                ORDER BY modelo
            """)
            return [{"id": v[0], "modelo": v[1], "placa": v[2]} for v in cursor.fetchall()]
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
                    "origen": row[1],                   # Texto (opcional)
                    "origen_lat": row[2],               # Coordenada (capturada por GPS)
                    "origen_lon": row[3],
                    "destino": row[4],                  # Texto (visible en UI)
                    "destino_lat": row[5],              # Coordenadas desde mapa
                    "destino_lon": row[6],
                    "fecha": row[7],
                    "hora_salida": row[8],
                    "hora_llegada": row[9],
                    "conductor": row[10],
                    "vehiculo": row[11],
                    "duracion": calcular_duracion(row[8], row[9]) if row[9] else None
                })
    except Exception as e:
        print("Error al obtener rutas programadas:", e)
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