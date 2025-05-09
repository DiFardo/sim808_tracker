import os
from werkzeug.utils import secure_filename
from bd_conexion import obtener_conexion

UPLOAD_FOLDER = 'static/img/vehiculos'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def agregar_vehiculo(placa, modelo, marca, anio, archivo_imagen=None):
    conexion = obtener_conexion()
    nombre_imagen = None

    # Procesar imagen si se adjuntó
    if archivo_imagen and allowed_file(archivo_imagen.filename):
        nombre_seguro = secure_filename(archivo_imagen.filename)
        ruta_imagen = os.path.join(UPLOAD_FOLDER, nombre_seguro)
        archivo_imagen.save(ruta_imagen)
        nombre_imagen = ruta_imagen  # Puedes guardar solo el nombre si prefieres

    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                INSERT INTO vehiculos (placa, modelo, marca, anio, imagen)
                VALUES (%s, %s, %s, %s, %s)
            """, (placa, modelo, marca, anio, nombre_imagen))
        conexion.commit()
        return True, "Vehículo registrado correctamente"
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

    if archivo_imagen and allowed_file(archivo_imagen.filename):
        nombre_seguro = secure_filename(archivo_imagen.filename)
        ruta_imagen = os.path.join(UPLOAD_FOLDER, nombre_seguro)
        archivo_imagen.save(ruta_imagen)
        nombre_imagen = ruta_imagen

    try:
        with conexion.cursor() as cursor:
            if nombre_imagen:
                cursor.execute("""
                    UPDATE vehiculos
                    SET placa = %s, modelo = %s, marca = %s, anio = %s, imagen = %s, estado = %s
                    WHERE id = %s
                """, (placa, modelo, marca, anio, nombre_imagen, estado, id_vehiculo))
            else:
                cursor.execute("""
                    UPDATE vehiculos
                    SET placa = %s, modelo = %s, marca = %s, anio = %s, estado = %s
                    WHERE id = %s
                """, (placa, modelo, marca, anio, estado, id_vehiculo))

        conexion.commit()
        return True, "Vehículo actualizado correctamente"

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
        with conexion.cursor() as cursor:
            cursor.execute("DELETE FROM vehiculos WHERE id = %s", (id_vehiculo,))
        conexion.commit()
        return True, "Vehículo eliminado correctamente"
    except Exception as e:
        conexion.rollback()
        return False, f"Error al eliminar vehículo: {str(e)}"
    finally:
        conexion.close()

