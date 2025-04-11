from bd_conexion import obtener_conexion

def obtener_usuario(dni_usuario):
    conexion = obtener_conexion()
    usuario = None
    with conexion.cursor() as cursor:
        cursor.execute(
            """
            SELECT u.id AS usuario_id, 
                   u.dni, 
                   u.pass, 
                   u.token, 
                   CONCAT(p.nombre, ' ', p.apellido) AS nombre_completo, 
                   r.nombre AS rol_nombre, 
                   COALESCE(p.imagen, '/static/img/default-profile.png') AS imagen,
                   r.id AS rol_id
            FROM usuarios u
            JOIN personas p ON u.id_persona = p.id
            LEFT JOIN roles r ON p.id_rol = r.id
            WHERE u.dni = %s
            """, (dni_usuario,))
        usuario = cursor.fetchone()
    conexion.close()
    return usuario
