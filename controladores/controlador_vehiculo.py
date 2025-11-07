import os
from werkzeug.utils import secure_filename
from bd_conexion import obtener_conexion
from pymysql.err import IntegrityError


UPLOAD_FOLDER = 'static/img/vehiculos'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

import re
from pymysql.err import IntegrityError

def normalizar_placa(placa: str) -> str:
    # quita espacios internos y externos y a MAYÚSCULAS
    p = (placa or "").strip().upper()
    p = re.sub(r"\s+", "", p)
    return p

def existe_placa(conexion, placa_norm: str) -> bool:
    with conexion.cursor() as cursor:
        cursor.execute("SELECT 1 FROM vehiculos WHERE placa=%s LIMIT 1", (placa_norm,))
        return cursor.fetchone() is not None

def existe_placa_otro(conexion, placa_norm: str, id_vehiculo: int) -> bool:
    with conexion.cursor() as cursor:
        cursor.execute("""
            SELECT 1 FROM vehiculos
            WHERE placa=%s AND id<>%s
            LIMIT 1
        """, (placa_norm, id_vehiculo))
        return cursor.fetchone() is not None


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def agregar_vehiculo(placa, modelo, marca, anio, archivo_imagen=None):
    conexion = obtener_conexion()
    nombre_imagen = None
    placa_norm = normalizar_placa(placa)
    if archivo_imagen and allowed_file(archivo_imagen.filename):
        nombre_seguro = secure_filename(archivo_imagen.filename)
        ruta_imagen = os.path.join(UPLOAD_FOLDER, nombre_seguro)
        archivo_imagen.save(ruta_imagen)
        nombre_imagen = ruta_imagen 
    try:
        if existe_placa(conexion, placa_norm):
            return False, "La placa ya está registrada."
        with conexion.cursor() as cursor:
            cursor.execute("""
                INSERT INTO vehiculos (placa, modelo, marca, anio, imagen, estado)
                VALUES (%s, %s, %s, %s, %s, 1)
            """, (placa_norm, modelo, marca, anio, nombre_imagen))
        conexion.commit()
        return True, "Vehículo registrado correctamente"
    except IntegrityError as e:
        if getattr(e, 'args', []) and len(e.args) > 0 and "1062" in str(e.args[0]):
            conexion.rollback()
            return False, "La placa ya está registrada."
        conexion.rollback()
        return False, f"Error al registrar vehículo: {str(e)}"
    except Exception as e:
        conexion.rollback()
        return False, f"Error al registrar vehículo: {str(e)}"
    finally:
        conexion.close()



def obtener_vehiculos():
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    id, placa, modelo, marca, anio, estado, imagen
                FROM vehiculos
                ORDER BY id 
            """)
            vehiculos = cursor.fetchall()
            lista = []
            for v in vehiculos:
                lista.append({
                    "id": v[0],
                    "placa": v[1],
                    "modelo": v[2],
                    "marca": v[3],
                    "anio": v[4],
                    "estado": v[5],
                    "imagen": v[6]
                })
            return lista
    except Exception as e:
        print("Error al obtener vehículos:", e)
        return []
    finally:
        conexion.close()


def editar_vehiculo(id_vehiculo, placa, modelo, marca, anio, estado, archivo_imagen=None):
    conexion = obtener_conexion()
    nombre_imagen = None
    placa_norm = normalizar_placa(placa)

    if archivo_imagen and allowed_file(archivo_imagen.filename):
        nombre_seguro = secure_filename(archivo_imagen.filename)
        ruta_imagen = os.path.join(UPLOAD_FOLDER, nombre_seguro)
        archivo_imagen.save(ruta_imagen)
        nombre_imagen = ruta_imagen

    try:
        # Evita duplicados con otros registros
        if existe_placa_otro(conexion, placa_norm, id_vehiculo):
            return False, "La placa ya pertenece a otro vehículo."

        with conexion.cursor() as cursor:
            if nombre_imagen:
                cursor.execute("""
                    UPDATE vehiculos
                    SET placa=%s, modelo=%s, marca=%s, anio=%s, imagen=%s, estado=%s
                    WHERE id=%s
                """, (placa_norm, modelo, marca, anio, nombre_imagen, estado, id_vehiculo))
            else:
                cursor.execute("""
                    UPDATE vehiculos
                    SET placa=%s, modelo=%s, marca=%s, anio=%s, estado=%s
                    WHERE id=%s
                """, (placa_norm, modelo, marca, anio, estado, id_vehiculo))

        conexion.commit()
        return True, "Vehículo actualizado correctamente"

    except IntegrityError as e:
        if getattr(e, 'args', []) and len(e.args) > 0 and "1062" in str(e.args[0]):
            conexion.rollback()
            return False, "La placa ya pertenece a otro vehículo."
        conexion.rollback()
        return False, f"Error al actualizar vehículo: {str(e)}"
    except Exception as e:
        conexion.rollback()
        return False, f"Error al actualizar vehículo: {str(e)}"
    finally:
        conexion.close()



def obtener_vehiculo_por_id(id_vehiculo):
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT id, placa, modelo, marca, anio, estado, imagen
                FROM vehiculos
                WHERE id = %s
            """, (id_vehiculo,))
            v = cursor.fetchone()
            if v:
                return {
                    "id": v[0],
                    "placa": v[1],
                    "modelo": v[2],
                    "marca": v[3],
                    "anio": v[4],
                    "estado": v[5],
                    "imagen": v[6]
                }
            return None
    except Exception as e:
        print("Error al obtener vehículo por ID:", e)
        return None
    finally:
        conexion.close()

def eliminar_vehiculo(id_vehiculo):
    conexion = obtener_conexion()
    try:
        # 1) ¿tiene recorrido/activo?
        if vehiculo_en_recorrido(conexion, id_vehiculo):
            return False, "NO_PERMITIDO_EN_RECORRIDO"

        # 2) Borrar
        with conexion.cursor() as cursor:
            cursor.execute("DELETE FROM vehiculos WHERE id = %s", (id_vehiculo,))
        conexion.commit()
        return True, "Vehículo eliminado correctamente"

    except IntegrityError as e:
        conexion.rollback()
        # Si tienes FKs y salta 1451
        if "1451" in str(e):
            return False, "NO_PERMITIDO_FK"
        return False, f"ERROR_INTEGRITY: {e}"
    except Exception as e:
        conexion.rollback()
        return False, f"ERROR: {e}"
    finally:
        conexion.close()


# Estados que bloquean eliminación por “recorrido” o “en espera”
ESTADOS_ENVIO_BLOQUEO = ("vehiculo_iniciar", "vehiculo_iniciado")

def vehiculo_en_recorrido(conexion, id_vehiculo: int) -> bool:
    """
    Bloquea si:
      - existe una asignación con estado = 'Activa' (aunque estado_envio sea NULL)
      - o estado_envio en ('vehiculo_iniciar','vehiculo_iniciado')
    """
    sql = """
        SELECT 1
        FROM asignacion_ruta_conductor
        WHERE id_vehiculo = %s
          AND (
                estado = %s
                OR estado_envio IN (%s, %s)
              )
        LIMIT 1
    """
    params = (id_vehiculo, 'Activa', *ESTADOS_ENVIO_BLOQUEO)
    with conexion.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone() is not None
