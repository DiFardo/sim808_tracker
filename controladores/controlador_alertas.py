from bd_conexion import obtener_conexion

def obtener_configuracion_alertas():
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    alerta_origen, alerta_distancia_total, 
                    alerta_distancia_restante, alerta_llegada, 
                    alerta_desvio, estado
                FROM config_alertas
                LIMIT 1;
            """)
            fila = cursor.fetchone()
            if fila:
                return {
                    "alerta_origen": fila[0],
                    "alerta_distancia_total": fila[1],
                    "alerta_distancia_restante": fila[2],
                    "alerta_llegada": fila[3],
                    "alerta_desvio": fila[4],
                    "estado": fila[5]
                }
            else:
                # Configuración por defecto si aún no existe
                return {
                    "alerta_origen": True,
                    "alerta_distancia_total": True,
                    "alerta_distancia_restante": True,
                    "alerta_llegada": True,
                    "alerta_desvio": True,
                    "estado": True
                }
    except Exception as e:
        print("❌ Error al obtener configuración de alertas:", e)
        return {}
    finally:
        conexion.close()


def obtener_configuracion_alertas():
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    alerta_origen, alerta_distancia_total, 
                    alerta_distancia_restante, alerta_llegada, 
                    alerta_desvio, estado
                FROM config_alertas
                LIMIT 1;
            """)
            fila = cursor.fetchone()
            if fila:
                return {
                    "alerta_origen": fila[0],
                    "alerta_distancia_total": fila[1],
                    "alerta_distancia_restante": fila[2],
                    "alerta_llegada": fila[3],
                    "alerta_desvio": fila[4],
                    "estado": fila[5]
                }
            else:
                # Configuración por defecto si aún no existe
                return {
                    "alerta_origen": True,
                    "alerta_distancia_total": True,
                    "alerta_distancia_restante": True,
                    "alerta_llegada": True,
                    "alerta_desvio": True,
                    "estado": True
                }
    except Exception as e:
        print("❌ Error al obtener configuración de alertas:", e)
        return {}
    finally:
        conexion.close()

def dar_baja_alertas():
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("UPDATE config_alertas SET estado = FALSE;")
        conexion.commit()
        return True
    except Exception as e:
        print("❌ Error al desactivar las alertas:", e)
        return False
    finally:
        conexion.close()
        

def activar_alertas():
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("UPDATE config_alertas SET estado = TRUE;")
        conexion.commit()
        return True
    except Exception as e:
        print("❌ Error al activar las alertas:", e)
        return False
    finally:
        conexion.close()
