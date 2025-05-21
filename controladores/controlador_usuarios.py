from bd_conexion import obtener_conexion
from werkzeug.security import generate_password_hash
import psycopg2.extras
def obtener_usuario(dni_usuario):
    conexion = obtener_conexion()
    usuario = None
    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute(
            """
            SELECT u.id AS usuario_id, 
                   u.dni, 
                   u.pass, 
                   u.token, 
                   CONCAT(p.nombre, ' ', p.apellido) AS nombre_completo, 
                   r.nombre AS rol_nombre, 
                   COALESCE(p.imagen, '/static/img/default-profile.png') AS imagen,
                   r.id AS rol_id,
                   p.id AS persona_id,
                   p.superusuario  -- agregar aquí
            FROM usuarios u
            JOIN personas p ON u.id_persona = p.id
            LEFT JOIN roles r ON p.id_rol = r.id
            WHERE u.dni = %s
            """, (dni_usuario,))
        usuario = cursor.fetchone()
    conexion.close()
    return usuario


def obtener_todos_usuarios():
    conexion = obtener_conexion()
    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute(
            """
            SELECT u.id AS usuario_id, 
                   u.dni, 
                   u.pass, 
                   u.token, 
                   CONCAT(p.nombre, ' ', p.apellido) AS nombre_completo, 
                   r.nombre AS rol_nombre, 
                   COALESCE(p.imagen, '/static/img/default-profile.png') AS imagen,
                   r.id AS rol_id,
                   p.id AS persona_id,
                   p.superusuario
            FROM usuarios u
            JOIN personas p ON u.id_persona = p.id
            LEFT JOIN roles r ON p.id_rol = r.id
            WHERE p.estado = TRUE
            ORDER BY p.nombre, p.apellido
            """
        )
        usuarios = cursor.fetchall()
    conexion.close()
    return usuarios

def obtener_roles_activos():
    conexion = obtener_conexion()
    with conexion.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute("""
            SELECT id, nombre
            FROM roles
            WHERE estado = TRUE
            ORDER BY nombre
        """)
        roles = cursor.fetchall()
    conexion.close()
    return roles



def obtener_usuarios_por_rol():
    conexion = obtener_conexion()
    usuarios = {"Administrador": [], "Conductor": []}

    with conexion.cursor() as cursor:
        cursor.execute("""
            SELECT 
                u.id AS usuario_id,
                u.dni,
                p.nombre,
                p.apellido,
                r.nombre AS rol,
                CASE 
                    WHEN p.id_rol IS NOT NULL THEN 'Activo'
                    ELSE 'Inactivo'
                END AS estado,
                COALESCE(p.imagen, '/static/img/default-profile.png') AS imagen
            FROM usuarios u
            JOIN personas p ON u.id_persona = p.id
            LEFT JOIN roles r ON p.id_rol = r.id
            ORDER BY r.nombre, p.apellido;
        """)

        for fila in cursor.fetchall():
            rol = fila[4]
            if rol in usuarios:  # solo 'Administrador' y 'Conductor'
                usuarios[rol].append({
                    "id": fila[0],
                    "dni": fila[1],
                    "nombre": fila[2],
                    "apellido": fila[3],
                    "rol": rol,
                    "estado": fila[5],
                    "imagen": fila[6]
                })

    conexion.close()
    return usuarios

def obtener_usuario_por_id(id_usuario):
    conexion = obtener_conexion()
    usuario = None

    with conexion.cursor() as cursor:
        cursor.execute("""
            SELECT u.id AS usuario_id, 
                   p.nombre, 
                   p.apellido, 
                   p.dni, 
                   p.estado, 
                   r.id AS rol_id
            FROM usuarios u
            JOIN personas p ON u.id_persona = p.id
            JOIN roles r ON p.id_rol = r.id
            WHERE u.id = %s
        """, (id_usuario,))
        fila = cursor.fetchone()

        if fila:
            usuario = {
                "id": fila[0],
                "nombre": fila[1],
                "apellido": fila[2],
                "dni": fila[3],
                "estado": fila[4],
                "rol_id": fila[5]
            }

    conexion.close()
    return usuario


def agregar_usuario(nombre, apellido, dni, password, rol_id, estado=True):
    conexion = obtener_conexion()
    nuevo_id = None

    try:
        with conexion.cursor() as cursor:
            # 1. Insertar en personas
            cursor.execute("""
                INSERT INTO personas (nombre, apellido, dni, id_rol, estado)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
            """, (nombre, apellido, dni, rol_id, estado))
            id_persona = cursor.fetchone()[0]

            # 2. Insertar en usuarios
            hashed_password = generate_password_hash(password)
            cursor.execute("""
                INSERT INTO usuarios (nombre, pass, dni, id_persona)
                VALUES (%s, %s, %s, %s);
            """, (dni, hashed_password, dni, id_persona))

        conexion.commit()
        nuevo_id = id_persona

    except Exception as e:
        conexion.rollback()
        raise e

    finally:
        conexion.close()

    return nuevo_id


def editar_usuario(id_usuario, nombre, apellido, dni, rol_id, estado, password=None):
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            # 1. Actualizar tabla personas
            cursor.execute("""
                UPDATE personas
                SET nombre = %s, apellido = %s, dni = %s, id_rol = %s, estado = %s
                WHERE id = (
                    SELECT id_persona FROM usuarios WHERE id = %s
                );
            """, (nombre, apellido, dni, rol_id, estado, id_usuario))

            # 2. Actualizar tabla usuarios
            if password:
                hashed = generate_password_hash(password)
                cursor.execute("""
                    UPDATE usuarios
                    SET dni = %s, pass = %s
                    WHERE id = %s;
                """, (dni, hashed, id_usuario))
            else:
                cursor.execute("""
                    UPDATE usuarios
                    SET dni = %s
                    WHERE id = %s;
                """, (dni, id_usuario))

        conexion.commit()
        return True

    except Exception as e:
        conexion.rollback()
        raise e

    finally:
        conexion.close()

def eliminar_usuario(id_usuario):
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            # Eliminar primero de 'usuarios'
            cursor.execute("DELETE FROM usuarios WHERE id = %s", (id_usuario,))
        conexion.commit()
        return True
    except Exception as e:
        conexion.rollback()
        raise e
    finally:
        conexion.close()


def actualizar_estado_usuario(id_usuario, nuevo_estado):
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                UPDATE personas
                SET estado = %s
                WHERE id = (
                    SELECT id_persona FROM usuarios WHERE id = %s
                )
            """, (nuevo_estado, id_usuario))
        conexion.commit()
        return True
    except Exception as e:
        conexion.rollback()
        raise e
    finally:
        conexion.close()
