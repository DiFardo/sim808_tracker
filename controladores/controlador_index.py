from bd_conexion import obtener_conexion
from datetime import datetime
import pytz

def obtener_rutas_hoy():
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            # Ajustar zona horaria para la sesión
            cur.execute("SET TIME ZONE 'America/Lima';")
            
            # Obtener la fecha actual en zona local y pasarla explícitamente a la consulta
            zona = pytz.timezone('America/Lima')
            fecha_local = datetime.now(zona).date()

            cur.execute("""
                SELECT 
                    p.nombre || ' ' || p.apellido AS conductor, 
                    rp.destino
                FROM asignacion_ruta_conductor arc
                JOIN personas p ON arc.id_persona = p.id
                JOIN rutas_programadas rp ON arc.id_ruta = rp.id
                WHERE rp.fecha = %s
                  AND arc.estado = 'Activa'
                ORDER BY p.nombre;
            """, (fecha_local,))

            resultados = cur.fetchall()
            columnas = [desc[0] for desc in cur.description]
            return [dict(zip(columnas, fila)) for fila in resultados]
    finally:
        conn.close()


def obtener_vehiculos_en_ruta():
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT v.placa, COUNT(*) AS cantidad_asignada
                FROM asignacion_ruta_conductor arc
                JOIN vehiculos v ON arc.id_vehiculo = v.id
                WHERE arc.estado = 'Activa'
                GROUP BY v.placa
            """)
            resultados = cur.fetchall()
            columnas = [desc[0] for desc in cur.description]
            return [dict(zip(columnas, fila)) for fila in resultados]
    finally:
        conn.close()

def obtener_conductores_activos_con_asignacion():
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    p.id,
                    p.nombre,
                    p.apellido,
                    p.dni,
                    CASE 
                        WHEN arc.estado = 'Activa' THEN TRUE
                        ELSE FALSE
                    END AS asignado
                FROM personas p
                LEFT JOIN asignacion_ruta_conductor arc ON p.id = arc.id_persona AND arc.estado = 'Activa'
                WHERE p.estado = TRUE
                ORDER BY asignado DESC, p.nombre;
            """)
            resultados = cur.fetchall()
            columnas = [desc[0] for desc in cur.description]
            return [dict(zip(columnas, fila)) for fila in resultados]
    finally:
        conn.close()


def obtener_conductores_en_ruta():
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT p.id, p.nombre, p.apellido, p.dni
                FROM asignacion_ruta_conductor arc
                JOIN personas p ON arc.id_persona = p.id
                WHERE arc.estado = 'Activa'
            """)
            resultados = cur.fetchall()
            columnas = [desc[0] for desc in cur.description]
            return [dict(zip(columnas, fila)) for fila in resultados]
    finally:
        conn.close()



def obtener_flotas_estado():
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            # Flotas activas
            cur.execute("""
                SELECT id, placa, modelo, marca, anio
                FROM vehiculos
                WHERE estado = TRUE;
            """)
            activas = cur.fetchall()
            columnas = [desc[0] for desc in cur.description]
            flotas_activas = [dict(zip(columnas, fila)) for fila in activas]

            # Flotas inactivas
            cur.execute("""
                SELECT id, placa, modelo, marca, anio
                FROM vehiculos
                WHERE estado = FALSE;
            """)
            inactivas = cur.fetchall()
            flotas_inactivas = [dict(zip(columnas, fila)) for fila in inactivas]

            return flotas_activas, flotas_inactivas
    finally:
        conn.close()


def contar_flotas_por_estado():
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT estado, COUNT(*) AS cantidad
                FROM vehiculos
                GROUP BY estado;
            """)
            resultados = cur.fetchall()
            return {estado: cantidad for estado, cantidad in resultados}
    finally:
        conn.close()

def dias_con_mas_rutas(limit=5):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT fecha, COUNT(*) as total_rutas
                FROM rutas_programadas
                GROUP BY fecha
                ORDER BY total_rutas DESC
                LIMIT %s;
            """, (limit,))
            resultados = cur.fetchall()
            columnas = [desc[0] for desc in cur.description]
            return [dict(zip(columnas, fila)) for fila in resultados]
    finally:
        conn.close()