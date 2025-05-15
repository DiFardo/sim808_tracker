from flask import Flask, render_template, request, redirect, flash, make_response, url_for, jsonify
from flask_jwt_extended import JWTManager, create_access_token, set_access_cookies, unset_jwt_cookies, jwt_required, get_jwt_identity, exceptions
import hashlib
import os
from datetime import timedelta
import json
import controladores.controlador_usuarios as controlador_usuarios
import controladores.controlador_vehiculo as controlador_vehiculo
import controladores.controlador_rutas as controlador_rutas
from bd_conexion import obtener_conexion

from controladores.controlador_vehiculo import agregar_vehiculo, obtener_vehiculos
from werkzeug.security import check_password_hash


app = Flask(__name__, static_url_path='/static', static_folder='static')
from flask_jwt_extended import JWTManager
app.secret_key = 'super-secret'
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_COOKIE_SECURE'] = False  # Pon True si usas HTTPS
app.config['JWT_ACCESS_COOKIE_NAME'] = 'access_token_cookie'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=2)
app.config['JWT_COOKIE_CSRF_PROTECT'] = False  # Pon True si usarás CSRF con cookies
app.url_map.strict_slashes = False


jwt = JWTManager(app)


# Ruta para la página de inicio de sesión
@app.route("/")
@app.route("/login_user")
def login():
    resp = make_response(render_template("login_user.html"))
    unset_jwt_cookies(resp)  # Limpia las cookies previas
    return resp

@app.route("/procesar_login", methods=["POST"])
def procesar_login():
    try:
        dni_usuario = request.form["dni_usuario"].strip()
        password = request.form["password"].strip()

        usuario = controlador_usuarios.obtener_usuario(dni_usuario)
        if not usuario:
            flash("Usuario no encontrado.")
            return redirect("/login_user")

        hash_guardado = usuario[2]  # campo `pass`
        if check_password_hash(hash_guardado, password):
            access_token = create_access_token(identity=dni_usuario)
            resp = make_response(redirect("/index"))
            set_access_cookies(resp, access_token)
            return resp
        else:
            flash("Contraseña incorrecta.")
            return redirect("/login_user")
    except Exception as e:
        flash(f"Ocurrió un error: {str(e)}")
        return redirect("/login_user")


@app.route("/procesar_logout")
def procesar_logout():
    resp = make_response(redirect("/login_user"))
    unset_jwt_cookies(resp)
    flash("Sesión cerrada correctamente.")
    return resp
# Página de inicio protegida
@app.route("/index")
@jwt_required()
def index():
    dni_usuario = get_jwt_identity()
    usuario = controlador_usuarios.obtener_usuario(dni_usuario)
    return render_template("index.html", usuario=usuario)

# USUARIOS
@app.route("/usuarios")
@jwt_required()
def usuarios():
    dni_usuario = get_jwt_identity()
    usuario = controlador_usuarios.obtener_usuario(dni_usuario)
    usuarios_por_rol = controlador_usuarios.obtener_usuarios_por_rol()
    return render_template("usuarios.html", 
                           usuario=usuario,
                           usuarios_admin=usuarios_por_rol.get("Administrador", []),
                           usuarios_conductor=usuarios_por_rol.get("Conductor", []))

#OBTENER USUARIOS
@app.route('/api/usuarios/<int:id_usuario>', methods=['GET'])
@jwt_required()
def api_obtener_usuario_por_id(id_usuario):
    try:
        usuario = controlador_usuarios.obtener_usuario_por_id(id_usuario)
        if usuario:
            return jsonify(usuario)
        else:
            return jsonify({"success": False, "message": "Usuario no encontrado"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# API: Registrar nuevo usuario
@app.route("/api/usuarios", methods=["POST"])
@jwt_required()
def api_registrar_usuario():
    data = request.json

    nombre = data.get("nombre")
    apellido = data.get("apellido")
    dni = data.get("dni")
    password = data.get("password")
    rol_id = int(data.get("rol_id"))
    estado = data.get("estado", "activo").lower() == "activo"

    try:
        nuevo_id = controlador_usuarios.agregar_usuario(nombre, apellido, dni, password, rol_id, estado)
        return jsonify({"success": True, "message": "Usuario registrado correctamente", "id": nuevo_id})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error al registrar usuario: {str(e)}"}), 400
# API: Editar usuario    
@app.route("/api/usuarios/<int:id_usuario>", methods=["PUT"])
@jwt_required()
def api_editar_usuario(id_usuario):
    data = request.json
    nombre = data.get("nombre")
    apellido = data.get("apellido")
    dni = data.get("dni")
    rol_id = int(data.get("rol_id"))
    estado = data.get("estado", "activo").lower() == "activo"
    password = data.get("password")  # puede venir vacío

    try:
        controlador_usuarios.editar_usuario(id_usuario, nombre, apellido, dni, rol_id, estado, password)
        return jsonify({"success": True, "message": "Usuario actualizado correctamente"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error al actualizar: {str(e)}"}), 400

@app.route("/api/usuarios/<int:id_usuario>", methods=["DELETE"])
@jwt_required()
def api_eliminar_usuario(id_usuario):
    try:
        controlador_usuarios.eliminar_usuario(id_usuario)
        return jsonify({"success": True, "message": "Usuario eliminado correctamente"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/usuarios/<int:id_usuario>/estado', methods=['PUT'])
@jwt_required()
def api_actualizar_estado_usuario(id_usuario):
    data = request.get_json()
    estado_str = data.get("estado", "").lower()
    if estado_str not in ["activo", "inactivo"]:
        return jsonify({"success": False, "message": "Estado inválido"}), 400

    nuevo_estado = True if estado_str == "activo" else False

    try:
        controlador_usuarios.actualizar_estado_usuario(id_usuario, nuevo_estado)
        return jsonify({"success": True, "message": "Estado actualizado correctamente"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# VEHICULOS 
@app.route("/vehiculos")
@jwt_required()
def vehiculos():
    dni_usuario = get_jwt_identity()
    usuario = controlador_usuarios.obtener_usuario(dni_usuario)
    vehiculos = obtener_vehiculos()
    breadcrumbs = [
        {"name": "Inicio", "url": "/"},
        {"name": "Vehículos", "url": "/vehiculos"}
    ]
    return render_template("vehiculos.html", usuario=usuario, vehiculos=vehiculos, breadcrumbs=breadcrumbs)


@app.route("/api/vehiculos", methods=["GET"])
@jwt_required()
def api_obtener_vehiculos():
    try:
        vehiculos = obtener_vehiculos()
        return jsonify({"success": True, "vehiculos": vehiculos}), 200
    except Exception as e:
        return jsonify({"success": False, "message": f"Error al obtener vehículos: {str(e)}"}), 500

# agregar vehiculo
@app.route("/api/vehiculo/registrar", methods=["POST"])
@jwt_required()
def api_registrar_vehiculo():
    try:
        placa = request.form.get("placa")
        modelo = request.form.get("modelo")
        marca = request.form.get("marca")
        anio = request.form.get("anio")
        imagen = request.files.get("imagen")

        # Validación básica
        if not placa or not modelo or not marca or not anio:
            return jsonify({"success": False, "message": "Faltan datos obligatorios"}), 400

        success, message = agregar_vehiculo(placa, modelo, marca, anio, imagen)
        status = 200 if success else 500
        return jsonify({"success": success, "message": message}), status

    except Exception as e:
        return jsonify({"success": False, "message": f"Error inesperado: {str(e)}"}), 500


@app.route("/api/vehiculo/<int:id_vehiculo>", methods=["PUT"])
@jwt_required()
def api_editar_vehiculo(id_vehiculo):
    try:
        placa = request.form.get("placa")
        modelo = request.form.get("modelo")
        marca = request.form.get("marca")
        anio = request.form.get("anio")
        estado = request.form.get("estado")  # <- nuevo
        imagen = request.files.get("imagen")

        if not placa or not modelo or not marca or not anio or estado is None:
            return jsonify({"success": False, "message": "Faltan datos obligatorios"}), 400

        estado_bool = estado.lower() == "true" or estado == "1"

        success, message = controlador_vehiculo.editar_vehiculo(
            id_vehiculo, placa, modelo, marca, anio, estado_bool, imagen
        )
        status = 200 if success else 500
        return jsonify({"success": success, "message": message}), status

    except Exception as e:
        return jsonify({"success": False, "message": f"Error inesperado: {str(e)}"}), 500


@app.route("/api/vehiculo/<int:id_vehiculo>", methods=["GET"])
@jwt_required()
def api_obtener_vehiculo_por_id(id_vehiculo):
    try:
        vehiculo = controlador_vehiculo.obtener_vehiculo_por_id(id_vehiculo)
        if vehiculo:
            return jsonify(vehiculo), 200
        else:
            return jsonify({"success": False, "message": "Vehículo no encontrado"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": f"Error inesperado: {str(e)}"}), 500

@app.route("/api/vehiculo/<int:id_vehiculo>", methods=["DELETE"])
@jwt_required()
def api_eliminar_vehiculo(id_vehiculo):
    try:
        success, message = controlador_vehiculo.eliminar_vehiculo(id_vehiculo)
        status_code = 200 if success else 400
        return jsonify({"success": success, "message": message}), status_code
    except Exception as e:
        return jsonify({"success": False, "message": f"Error inesperado: {str(e)}"}), 500


# MAPA EN TIEMPO REAL
@app.route("/mapa_flotas")
@jwt_required()
def mapa_flotas():
    dni_usuario = get_jwt_identity()
    usuario = controlador_usuarios.obtener_usuario(dni_usuario)
    breadcrumbs = [
        {"name": "Inicio", "url": "/"},
        {"name": "Mapa", "url": "/mapa_flotas"}
    ]
    return render_template("mapa_flotas.html", usuario=usuario, breadcrumbs=breadcrumbs)



@app.route("/rutas_programadas")
@jwt_required()
def rutas_programadas():
    dni_usuario = get_jwt_identity()
    usuario = controlador_usuarios.obtener_usuario(dni_usuario)
    conductores = controlador_rutas.obtener_todos_los_conductores()
    vehiculos = controlador_rutas.obtener_vehiculos_disponibles()
    rutas = controlador_rutas.obtener_rutas_programadas()  # Asumiendo que ya tienes esta función

    breadcrumbs = [
        {"name": "Inicio", "url": "/"},
        {"name": "Rutas Programadas", "url": "/rutas_programadas"}
    ]

    return render_template("rutas_programadas.html",
                           usuario=usuario,
                           breadcrumbs=breadcrumbs,
                           rutas=rutas,
                           conductores=conductores,
                           vehiculos=vehiculos)



@app.route("/api/asignar_ruta", methods=["POST"])
@jwt_required()
def api_asignar_ruta():
    try:
        data = request.form

        id_persona = int(data.get("conductor"))
        id_vehiculo = int(data.get("vehiculo"))
        destino_completo = data.get("destino")  # Lo que viene del input destino
        destino_coords = data.get("destino_coords")
        fecha = data.get("fecha")
        hora_salida = data.get("hora_salida")

        if not all([id_persona, id_vehiculo, destino_completo, destino_coords, fecha, hora_salida]):
            return jsonify({"success": False, "message": "Faltan campos requeridos"}), 400

        try:
            destino_lat, destino_lon = map(float, destino_coords.split(","))
        except Exception:
            return jsonify({"success": False, "message": "Coordenadas de destino inválidas"}), 400

        # Puedes usar la dirección completa como 'destino' si ya no usas la corta
        destino = destino_completo  # o .split(",")[0] si quieres solo la calle

        success, msg, _ = controlador_rutas.registrar_ruta_y_asignacion(
            id_persona=id_persona,
            id_vehiculo=id_vehiculo,
            destino=destino,
            destino_lat=destino_lat,
            destino_lon=destino_lon,
            fecha=fecha,
            hora_salida=hora_salida
        )

        if success:
            return jsonify({"success": True, "message": "Ruta asignada correctamente"}), 200
        else:
            return jsonify({"success": False, "message": msg}), 500

    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500



@app.route("/api/ruta-actual", methods=["GET"])
def obtener_ruta_actual():
    id_vehiculo = request.args.get("id_vehiculo")
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT arc.id_ruta
                FROM asignacion_ruta_conductor arc
                JOIN rutas_programadas rp ON arc.id_ruta = rp.id
                WHERE arc.id_vehiculo = %s AND arc.estado = 'Activa'
                ORDER BY arc.asignado_en DESC
                LIMIT 1;
            """, (id_vehiculo,))
            resultado = cursor.fetchone()
            if resultado:
                return jsonify({"id_ruta": resultado[0]})
            else:
                return jsonify({"id_ruta": None}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conexion.close()

@app.route("/api/registrar_origen_gps", methods=["POST"])
@app.route("/api/registrar_origen_gps/", methods=["POST"])
def registrar_origen_gps():
    data = request.get_json()
    print("📦 Payload recibido:", data)

    try:
        id_ruta = int(data.get("id_ruta"))       # <- convertir a entero
        lat = float(data.get("lat"))             # <- convertir a decimal
        lon = float(data.get("lon"))
    except (TypeError, ValueError):
        return jsonify({"error": "Datos inválidos"}), 400

    direccion = f"Lat: {lat}, Lon: {lon}"

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                UPDATE rutas_programadas
                SET origen = %s,
                    origen_lat = %s,
                    origen_lon = %s
                WHERE id = %s;
            """, (direccion, lat, lon, id_ruta))
        conexion.commit()
        print(f"✅ Ruta {id_ruta} actualizada correctamente.")
        return jsonify({"success": True, "message": "Origen actualizado"}), 200
    except Exception as e:
        conexion.rollback()
        print("❌ Error al actualizar:", str(e))
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conexion.close()





if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)