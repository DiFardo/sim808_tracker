from bd_conexion import obtener_conexion
from flask import request, jsonify
import psycopg2.extras

# ======================
# PERMISOS_ROLES - CONTROLADORES
# ======================

def agregar_permiso_rol(id_rol, id_modulo, id_opcion=None, id_accion=None, permiso=True):
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    sql = """
        INSERT INTO permisos_roles (id_rol, id_modulo, id_opcion, id_accion, permiso)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (id_rol, id_modulo, id_opcion, id_accion) DO UPDATE SET permiso = EXCLUDED.permiso;
    """
    cursor.execute(sql, (id_rol, id_modulo, id_opcion, id_accion, permiso))
    conexion.commit()
    cursor.close()
    conexion.close()

def obtener_permisos_rol(id_rol):
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    sql = """
        SELECT pr.id_modulo, m.nombre AS modulo_nombre,
               pr.id_opcion, o.nombre AS opcion_nombre,
               pr.permiso
        FROM permisos_roles pr
        LEFT JOIN modulos m ON pr.id_modulo = m.id
        LEFT JOIN opciones o ON pr.id_opcion = o.id
        WHERE pr.id_rol = %s
        ORDER BY m.nombre, o.nombre;
    """
    cursor.execute(sql, (id_rol,))
    resultados = cursor.fetchall()
    cursor.close()
    conexion.close()
    return resultados


def es_superusuario(id_persona):
    # Esta función puede quedarse para validar si una persona es superusuario,
    # para permitirle administrar roles y permisos
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    sql = "SELECT superusuario FROM personas WHERE id = %s"
    cursor.execute(sql, (id_persona,))
    fila = cursor.fetchone()
    cursor.close()
    conexion.close()
    return fila and fila[0] is True

# ======================
# API para guardar permisos solo por rol
# ======================
def guardar_permisos_rol():
    data = request.get_json()
    id_rol = data.get('id_rol')
    permisos = data.get('permisos', [])

    if not id_rol or not isinstance(permisos, list):
        return jsonify({'error': 'Datos inválidos'}), 400

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    try:
        cursor.execute("DELETE FROM permisos_roles WHERE id_rol = %s", (id_rol,))

        sql_insert = """
            INSERT INTO permisos_roles (id_rol, id_modulo, id_opcion, permiso)
            VALUES (%s, %s, %s, TRUE)
        """
        for permiso in permisos:
            tipo = permiso.get('tipo')
            id_permiso = permiso.get('id')
            id_modulo = None
            id_opcion = None

            if tipo == 'modulo':
                id_modulo = id_permiso
            elif tipo == 'opcion':
                id_opcion = id_permiso
            else:
                continue

            cursor.execute(sql_insert, (id_rol, id_modulo, id_opcion))

        conexion.commit()
    except Exception as e:
        conexion.rollback()
        cursor.close()
        conexion.close()
        return jsonify({'error': str(e)}), 500

    cursor.close()
    conexion.close()
    return jsonify({'message': 'Permisos guardados correctamente'})





def obtener_modulos_con_opciones():
    conexion = obtener_conexion()
    cursor = conexion.cursor(cursor_factory=psycopg2.extras.DictCursor)
    sql = """
        SELECT m.id AS modulo_id, m.nombre AS modulo_nombre,
               o.id AS opcion_id, o.nombre AS opcion_nombre
        FROM modulos m
        LEFT JOIN opciones o ON o.id_modulo = m.id AND o.estado = TRUE
        WHERE m.estado = TRUE
        ORDER BY m.nombre, o.nombre
    """
    cursor.execute(sql)
    filas = cursor.fetchall()
    cursor.close()
    conexion.close()

    modulos = {}
    for fila in filas:
        mid = fila['modulo_id']
        if mid not in modulos:
            modulos[mid] = {
                "id": mid,
                "nombre": fila['modulo_nombre'],
                "opciones": []
            }
        if fila['opcion_id']:
            modulos[mid]['opciones'].append({
                "id": fila['opcion_id'],
                "nombre": fila['opcion_nombre']
            })

    return list(modulos.values())



def tiene_permiso(permisos, id_modulo=None, id_opcion=None):
    """
    Verifica si en la lista de permisos existe uno activo para el módulo/opción indicados.

    permisos: lista de tuplas con la estructura
        (id_modulo, modulo_nombre, id_opcion, opcion_nombre, permiso)
        NOTA: Si tienes más columnas, asegúrate de usar los índices correctos.
    id_modulo: int o None
    id_opcion: int o None

    Retorna True si el permiso está activo (True), False si no.
    """
    for p in permisos:
        if ((id_modulo is None or p[0] == id_modulo) and
            (id_opcion is None or p[2] == id_opcion) and
            p[4] == True):
            return True
    return False
