from flask import Flask, render_template, request, Blueprint, redirect, flash, make_response, url_for, jsonify 
from flask_jwt_extended import JWTManager,  create_access_token, set_access_cookies, unset_jwt_cookies, jwt_required, get_jwt_identity, exceptions, verify_jwt_in_request
import hashlib
import os
from datetime import timedelta
import json
import controladores.controlador_usuarios as controlador_usuarios
import controladores.controlador_vehiculo as controlador_vehiculo
import controladores.controlador_rutas as controlador_rutas
import controladores.controlador_index as controlador_index
import controladores.controlador_permisos as controlador_permisos
import controladores.controlador_mantenimiento as controlador_mantenimiento
import controladores.controlador_mantenimiento as cm
from controladores.controlador_permisos import obtener_permisos_rol, tiene_permiso
from controladores.controlador_index import obtener_flotas_estado, obtener_conductores_en_ruta, dias_con_mas_rutas, obtener_rutas_hoy, obtener_vehiculos_en_ruta, obtener_conductores_activos_con_asignacion
from werkzeug.security import check_password_hash

from bd_conexion import obtener_conexion
import requests
from datetime import datetime
from datetime import date
from flask import session
import psycopg2.extras

import serial

from pytz import timezone, utc

from controladores.controlador_vehiculo import agregar_vehiculo, obtener_vehiculos
from werkzeug.security import check_password_hash

import logging




app = Flask(__name__, static_url_path='/static', static_folder='static')

app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'super-secret-dev-key-change-in-prod')

app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False  
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_COOKIE_SECURE'] = False  # True en producción con HTTPS
app.config['JWT_ACCESS_COOKIE_NAME'] = 'access_token_cookie'
app.config['JWT_COOKIE_CSRF_PROTECT'] = False

app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=2)
app.url_map.strict_slashes = False
jwt = JWTManager(app)

def tiene_permiso(permisos, id_modulo=None, id_opcion=None):
    for p in permisos:
        if ((id_modulo is None or p[0] == id_modulo) and
            (id_opcion is None or p[2] == id_opcion) and
            p[4] == True):
            return True
    return False

app.jinja_env.globals.update(tiene_permiso=tiene_permiso)




# Resto de tus rutas (sin cambios funcionales)
@app.route('/verificar-conexion')
def verificar_conexion():
    try:
        conn = obtener_conexion()
        conn.close()
        return jsonify({"estado": "exitoso", "mensaje": "Conexión a la base de datos establecida correctamente."}), 200
    except Exception as e:
        return jsonify({"estado": "error", "mensaje": str(e)}), 500

def dni_valido(d: str) -> bool:
    return d.isdigit() and len(d) == 8

@app.route("/")
@app.route("/login_user")
def login():
    resp = make_response(render_template("login_user.html"))
    unset_jwt_cookies(resp)
    return resp

@app.route("/procesar_login", methods=["POST"])
def procesar_login():
    try:
        dni_usuario = request.form.get("dni_usuario","").strip()
        password    = request.form.get("password","").strip()

        if not (dni_usuario.isdigit() and len(dni_usuario) == 8):
            flash("El DNI debe tener 8 dígitos numéricos.", "error")
            return redirect("/login_user")
        usuario = controlador_usuarios.obtener_usuario(dni_usuario)
        if not usuario:
            flash("Usuario no encontrado.", "error")
            return redirect("/login_user")
        if usuario.get("persona_eliminado") is True:
            flash("Tu usuario fue eliminado. Contacta al administrador.", "error")
            return redirect("/login_user")
        if usuario.get("persona_estado") is not True:
            flash("Tu usuario está inactivo. Contacta al administrador.", "error")
            return redirect("/login_user")

        if not check_password_hash(usuario["pass"], password):
            flash("Contraseña incorrecta.", "error")
            return redirect("/login_user")
        session['rol']         = usuario["rol_nombre"]
        session['rol_id']      = usuario["rol_id"]
        session['dni_usuario'] = dni_usuario
        session['id_persona']  = usuario["persona_id"]

        access_token = create_access_token(identity=dni_usuario)
        resp = make_response(redirect("/index"))
        set_access_cookies(resp, access_token)
        return resp

    except Exception as e:
        flash(f"Ocurrió un error: {str(e)}", "error")
        return redirect("/login_user")




@app.route("/procesar_logout")
def procesar_logout():
    resp = make_response(redirect("/login_user"))
    unset_jwt_cookies(resp)
    flash("Sesión cerrada correctamente.")
    return resp

@app.route("/index")
@jwt_required()
def index():
    dni_usuario = get_jwt_identity()
    usuario = controlador_usuarios.obtener_usuario(dni_usuario)

    flotas_activas, flotas_inactivas = obtener_flotas_estado()
    cantidad_flotas = len(flotas_activas)
    cantidad_flotas_inactivas = len(flotas_inactivas)

    rutas_hoy = obtener_rutas_hoy()
    vehiculos_en_ruta = obtener_vehiculos_en_ruta()
    conductores_disponibles = obtener_conductores_activos_con_asignacion()
    conductores_en_ruta = obtener_conductores_en_ruta()

    dias_top_rutas = dias_con_mas_rutas()

    return render_template("index.html",
                           usuario=usuario,
                           flotas_activas=flotas_activas,
                           cantidad_flotas=cantidad_flotas,
                           cantidad_flotas_inactivas=cantidad_flotas_inactivas,
                           rutas_hoy=rutas_hoy,
                           vehiculos_en_ruta=vehiculos_en_ruta,
                           conductores_disponibles=conductores_disponibles,
                           conductores_en_ruta=conductores_en_ruta,
                           dias_top_rutas=dias_top_rutas)
    
@app.route("/permisos")
@jwt_required()
def permisos():
    dni_usuario = get_jwt_identity()
    usuario = controlador_usuarios.obtener_usuario(dni_usuario)

    if not controlador_permisos.es_superusuario(usuario['persona_id']):
        return "Acceso denegado", 403
    
    usuarios = controlador_usuarios.obtener_todos_usuarios()

    # Breadcrumb simple: Inicio / Permisos
    breadcrumbs = [
        {"name": "Inicio", "url": url_for("index")},
        {"name": "Permisos", "url": url_for("permisos")}
    ]

    return render_template(
        "permisos.html",
        usuario=usuario,
        usuarios=usuarios,
        breadcrumbs=breadcrumbs
    )



@app.route("/api/roles")
@jwt_required()
def api_roles():
    dni_usuario = get_jwt_identity()
    usuario = controlador_usuarios.obtener_usuario(dni_usuario)
    if not usuario or not usuario.get('superusuario', False):
        return jsonify({"error": "Acceso denegado"}), 403
    roles = controlador_usuarios.obtener_roles_activos()
    roles_json = [{"id": r["id"], "nombre": r["nombre"]} for r in roles]
    return jsonify(roles_json)


@app.route("/api/permisos-rol/<int:id_rol>")
@jwt_required()
def api_permisos_rol(id_rol):
    dni_usuario = get_jwt_identity()
    usuario_actual = controlador_usuarios.obtener_usuario(dni_usuario)
    if not usuario_actual or not usuario_actual.get('superusuario', False):
        return jsonify({"error": "Acceso denegado"}), 403
    resultados = controlador_permisos.obtener_permisos_rol(id_rol)
    permisos_rol = []
    for fila in resultados:
        permisos_rol.append({
            "id_modulo": fila[0],
            "modulo_nombre": fila[1],
            "id_opcion": fila[2], 
            "opcion_nombre": fila[3],  
            "permiso": fila[4]
        })
    return jsonify({
        "permisos_rol": permisos_rol
    })

@app.route("/api/guardar-permisos-rol", methods=["POST"])
@jwt_required()
def api_guardar_permisos_rol():
    dni_usuario = get_jwt_identity()
    usuario_actual = controlador_usuarios.obtener_usuario(dni_usuario)
    if not usuario_actual or not usuario_actual.get('superusuario', False):
        return jsonify({"error": "Acceso denegado"}), 403
    return controlador_permisos.guardar_permisos_rol()
@app.route('/api/modulos-opciones')
@jwt_required()
def api_modulos_opciones():
    dni_usuario = get_jwt_identity()
    usuario = controlador_usuarios.obtener_usuario(dni_usuario)
    if not usuario or not usuario.get('superusuario', False):
        return jsonify({"error": "Acceso denegado"}), 403
    modulos = controlador_permisos.obtener_modulos_con_opciones()
    return jsonify(modulos)



@app.route('/usuarios')
@jwt_required()
def usuarios():
    dni_usuario = get_jwt_identity()
    usuario = controlador_usuarios.obtener_usuario(dni_usuario)

    permisos = obtener_permisos_rol(usuario['rol_id'])

    mostrar_boton_añadir = tiene_permiso(permisos, id_modulo=1, id_opcion=1)  # módulo Usuarios, opción Agregar usuario
    mostrar_icono_editar = tiene_permiso(permisos, id_modulo=1, id_opcion=2)  # opción Editar usuario
    mostrar_icono_eliminar = tiene_permiso(permisos, id_modulo=1, id_opcion=3)  # opción Eliminar usuario
    mostrar_icono_estado = tiene_permiso(permisos, id_modulo=1, id_opcion=4)  # opción Cambiar estado usuario


    usuarios_por_rol = controlador_usuarios.obtener_usuarios_por_rol()

    return render_template('usuarios.html',
                       usuario=usuario,
                       usuarios_admin=usuarios_por_rol.get("Administrador", []),
                       usuarios_conductor=usuarios_por_rol.get("Conductor", []),
                       mostrar_boton_añadir=mostrar_boton_añadir,
                       mostrar_icono_editar=mostrar_icono_editar,
                       mostrar_icono_eliminar=mostrar_icono_eliminar,
                       mostrar_icono_estado=mostrar_icono_estado)  # <-- nueva variable


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


@app.route("/vehiculos")
@jwt_required()
def vehiculos():
    dni_usuario = get_jwt_identity()
    usuario = controlador_usuarios.obtener_usuario(dni_usuario)

    permisos = obtener_permisos_rol(usuario['rol_id'])

    # Usa los ID reales de la tabla permisos_roles
    mostrar_boton_añadir = tiene_permiso(permisos, id_modulo=2, id_opcion=9)
    mostrar_icono_editar = tiene_permiso(permisos, id_modulo=2, id_opcion=10)
    mostrar_icono_eliminar = tiene_permiso(permisos, id_modulo=2, id_opcion=11)
    mostrar_selector_estado = tiene_permiso(permisos, id_modulo=2, id_opcion=12)

    vehiculos = obtener_vehiculos()

    # Breadcrumb simple: Inicio / Vehículos
    breadcrumbs = [
        {"name": "Inicio", "url": url_for("index")},
        {"name": "Vehículos", "url": url_for("vehiculos")}
    ]

    return render_template(
        "vehiculos.html",
        usuario=usuario,
        vehiculos=vehiculos,
        mostrar_boton_añadir=mostrar_boton_añadir,
        mostrar_icono_editar=mostrar_icono_editar,
        mostrar_icono_eliminar=mostrar_icono_eliminar,
        mostrar_selector_estado=mostrar_selector_estado,
        breadcrumbs=breadcrumbs
    )




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
        ok, msg = controlador_vehiculo.eliminar_vehiculo(id_vehiculo)
        if ok:
            return jsonify({"success": True, "message": msg}), 200

        # Si el backend mandó nuestro código semántico, responde 409
        if isinstance(msg, str) and msg.startswith("NO_PERMITIDO_EN_RECORRIDO"):
            return jsonify({"success": False, "message": "El vehículo está en recorrido y no puede eliminarse."}), 409

        return jsonify({"success": False, "message": msg}), 500
    except Exception as e:
        return jsonify({"success": False, "message": f"Error inesperado: {str(e)}"}), 500



@app.route("/mapa_flotas")
@jwt_required()
def mapa_flotas():
    dni_usuario = get_jwt_identity()
    usuario = controlador_usuarios.obtener_usuario(dni_usuario)

    rutas_hoy = controlador_rutas.obtener_rutas_programadas_hoy()

    breadcrumbs = [
        {"name": "Inicio", "url": "/index"},
        {"name": "Mapa", "url": "/mapa_flotas"}
    ]
    return render_template(
        "mapa_flotas.html",
        usuario=usuario,
        rutas_hoy=rutas_hoy,
        breadcrumbs=breadcrumbs
    )






@app.route("/gestionar_rutas")
@jwt_required()
def gestionar_rutas():
    dni_usuario = get_jwt_identity()
    usuario = controlador_usuarios.obtener_usuario(dni_usuario)
    rutas = controlador_rutas.obtener_rutas_programadas()
    rutas_sin_conductor = controlador_rutas.obtener_rutas_sin_conductor()
    conductores = controlador_rutas.obtener_todos_los_conductores()
    vehiculos = controlador_rutas.obtener_todos_los_vehiculos_con_estado()
    asignaciones = controlador_rutas.obtener_conductores_asignados()  #

    breadcrumbs = [
        {"name": "Inicio", "url": "/index"},
        {"name": "Rutas Programadas", "url": "/rutas_programadas"}
    ]

    return render_template("gestionar_rutas.html",
                           usuario=usuario,
                           breadcrumbs=breadcrumbs,
                           rutas_programadas=rutas,
                           rutas_sin_conductor=rutas_sin_conductor,
                           conductores=conductores,
                           vehiculos=vehiculos,
                            asignaciones=asignaciones)
    

@app.route("/api/asignar_conductor", methods=["POST"])
@jwt_required()
def api_asignar_conductor():
    try:
        data = request.form
        id_ruta = int(data.get("ruta_id"))
        id_persona = int(data.get("conductor_id"))

        if not id_ruta or not id_persona:
            return jsonify({"success": False, "message": "Faltan datos obligatorios"}), 400

        success, msg = controlador_rutas.asignar_conductor_a_ruta(id_ruta, id_persona)
        if success:
            return jsonify({"success": True, "message": msg})
        else:
            return jsonify({"success": False, "message": msg}), 400

    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@app.route("/api/editar_ruta", methods=["POST"])
@jwt_required()
def api_editar_ruta():
    try:
        data = request.form

        id_ruta = int(data.get("ruta_id"))
        id_vehiculo = int(data.get("vehiculo"))
        destino = data.get("destino")
        destino_coords = data.get("destino_coords")
        fecha = data.get("fecha")

        if not all([id_ruta, id_vehiculo, destino, destino_coords, fecha]):
            return jsonify({"success": False, "message": "Faltan datos obligatorios"}), 400

        lat, lon = map(str.strip, destino_coords.split(","))

        puntos_importantes = None
        puntos_json = data.get("puntos_importantes")
        if puntos_json:
            import json
            puntos_importantes = json.loads(puntos_json)

        success, msg = controlador_rutas.editar_ruta_programada(
            id_ruta=id_ruta,
            id_vehiculo=id_vehiculo,
            destino_lat=lat,
            destino_lon=lon,
            destino=destino,
            fecha=fecha,
            puntos_importantes=puntos_importantes  # ✅ Si tu lógica usa puntos
        )

        if success:
            vehiculo = controlador_rutas.obtener_vehiculo_por_id(id_vehiculo)
            return jsonify({
                "success": True,
                "message": msg,
                "ruta": {
                    "id": id_ruta,
                    "destino": destino,
                    "fecha": fecha,
                    "lat": lat,
                    "lon": lon,
                    "vehiculo": f"{vehiculo['modelo']} - {vehiculo['placa']}" if vehiculo else "N/D",
                    "vehiculo_id": id_vehiculo,
                    "puntos_importantes": puntos_importantes or []
                }
            }), 200
        else:
            return jsonify({"success": False, "message": msg}), 400

    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500



@app.route("/api/editar_conductor", methods=["PUT"])
@jwt_required()
def api_editar_conductor():
    try:
        data = request.form or request.json
        id_ruta = int(data.get("ruta_id"))
        id_persona = int(data.get("conductor_id"))

        if not id_ruta or not id_persona:
            return jsonify({"success": False, "message": "Faltan datos obligatorios"}), 400

        success, msg = controlador_rutas.editar_conductor_de_ruta(id_ruta, id_persona)
        if success:
            return jsonify({"success": True, "message": msg})
        else:
            return jsonify({"success": False, "message": msg}), 400

    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500


@app.route("/api/ubicacion_actual")
def ubicacion_actual():
    id_ruta = request.args.get("id_ruta")
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT origen_lat, origen_lon
                FROM rutas_programadas
                WHERE id = %s
            """, (id_ruta,))
            row = cur.fetchone()
            if row:
                return jsonify({"success": True, "lat": row[0], "lon": row[1]})
            else:
                return jsonify({"success": False})
    finally:
        conn.close()

@app.route("/api/asignar_ruta", methods=["POST"])
@jwt_required()
def api_asignar_ruta():
    try:
        data = request.form
        id_vehiculo = int(data.get("vehiculo"))
        destino_completo = data.get("destino")
        destino_coords = data.get("destino_coords")
        fecha = date.today().isoformat()  # Usar fecha actual del servidor
        if not all([id_vehiculo, destino_completo, destino_coords]):
            return jsonify({"success": False, "message": "Faltan campos requeridos"}), 400
        try:
            destino_lat, destino_lon = map(float, destino_coords.split(","))
        except Exception:
            return jsonify({"success": False, "message": "Coordenadas de destino inválidas"}), 400
        puntos_importantes = None
        puntos_json = data.get("puntos_importantes")
        if puntos_json:
            try:
                import json
                puntos_importantes = json.loads(puntos_json)
            except Exception:
                return jsonify({"success": False, "message": "Formato de puntos importantes inválido"}), 400
        success, msg, id_ruta = controlador_rutas.registrar_ruta_solo_con_vehiculo(
            id_vehiculo=id_vehiculo,
            destino=destino_completo,
            destino_lat=destino_lat,
            destino_lon=destino_lon,
            fecha=fecha,
            puntos_importantes=puntos_importantes
        )
        puntos_guardados = []
        if success:
            conexion = obtener_conexion()
            try:
                with conexion.cursor() as cursor:
                    cursor.execute("""
                        SELECT nombre, lat, lon, orden
                        FROM puntos_importantes
                        WHERE id_ruta = %s
                        ORDER BY orden ASC;
                    """, (id_ruta,))
                    for row in cursor.fetchall():
                        puntos_guardados.append({
                            "nombre": row[0],
                            "lat": row[1],
                            "lon": row[2],
                            "orden": row[3]
                        })
            finally:
                conexion.close()
        vehiculo = controlador_rutas.obtener_vehiculo_por_id(id_vehiculo)
        if success:
            return jsonify({
                "success": True,
                "message": msg,
                "ruta": {
                    "id": id_ruta,
                    "destino": destino_completo,
                    "fecha": fecha,
                    "lat": destino_lat,
                    "lon": destino_lon,
                    "vehiculo": f"{vehiculo['modelo']} - {vehiculo['placa']}" if vehiculo else "N/D",
                    "vehiculo_id": id_vehiculo,
                    "puntos_importantes": puntos_guardados  
                }
            }), 200
        else:
            return jsonify({"success": False, "message": msg}), 500

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/vehiculos_disponibles")
def vehiculos_disponibles():
    id_asignado = request.args.get("id_asignado", type=int)
    vehiculos = controlador_rutas.obtener_vehiculos_disponibles(id_asignado)
    return jsonify(vehiculos)

@app.route("/api/registrar_desvio", methods=["POST"])
def registrar_desvio():
    try:
        data = request.get_json()
        id_ruta = int(data["id_ruta"])
        lat = float(data["lat"])
        lon = float(data["lon"])

        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("""
            INSERT INTO desvio_ruta (id_ruta, latitud, longitud)
            VALUES (%s, %s, %s)
        """, (id_ruta, lat, lon))
        conexion.commit()
        cursor.close()
        conexion.close()

        return jsonify({"success": True})
    except Exception as e:
        print("❌ Error al registrar desvío:", e)
        return jsonify({"success": False, "message": str(e)}), 500


    
@app.route("/api/ruta/<int:id_ruta>", methods=["DELETE"])
@jwt_required()
def eliminar_ruta_api(id_ruta):
    con = obtener_conexion()
    try:
        if controlador_rutas.ruta_en_recorrido(con, id_ruta):
            return jsonify({
                "success": False,
                "code": "EN_RECORRIDO",
                "message": "No se puede eliminar: la ruta está en recorrido/activa."
            }), 409

        success, msg = controlador_rutas.eliminar_ruta(id_ruta)
        if success:
            return jsonify({"success": True, "message": msg}), 200
        else:
            return jsonify({"success": False, "message": msg}), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        con.close()
    



# @app.route("/api/ruta/<int:id_ruta>", methods=["PUT"])
# @jwt_required()
# def editar_ruta_api(id_ruta):
#     try:
#         data = request.form

#         id_persona = int(data.get("conductor"))
#         id_vehiculo = int(data.get("vehiculo"))
#         destino = data.get("destino")
#         destino_coords = data.get("destino_coords")
#         fecha = data.get("fecha")

#         if not all([id_persona, id_vehiculo, destino, destino_coords, fecha]):
#             return jsonify({"success": False, "message": "Faltan campos requeridos"}), 400

#         try:
#             destino_lat, destino_lon = map(float, destino_coords.split(","))
#         except ValueError:
#             return jsonify({"success": False, "message": "Coordenadas inválidas"}), 400

#         success, msg = controlador_rutas.editar_ruta(
#             id_ruta=id_ruta,
#             id_persona=id_persona,
#             id_vehiculo=id_vehiculo,
#             destino=destino,
#             destino_lat=destino_lat,
#             destino_lon=destino_lon,
#             fecha=fecha
#         )

#         if success:
#             return jsonify({"success": True, "message": msg}), 200
#         else:
#             return jsonify({"success": False, "message": msg}), 500

#     except Exception as e:
#         return jsonify({"success": False, "message": str(e)}), 500

## APIS PARA REPUESTAS DEL MODULO SIM 808 

@app.route("/api/ruta-actual", methods=["GET"])
def obtener_ruta_actual():
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT arc.id_ruta
                FROM asignacion_ruta_conductor arc
                WHERE arc.estado_envio = 'vehiculo_iniciar'
                ORDER BY arc.asignado_en DESC
                LIMIT 1;
            """)
            resultado = cursor.fetchone()
            if resultado:
                return jsonify({"id_ruta": resultado[0]}), 200
            else:
                return jsonify({"id_ruta": None}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conexion.close()
        
        
@app.route('/api/guardar_trazado_real', methods=['POST'])
def guardar_trazado_real():
    data = request.json
    id_ruta = data.get('id_ruta')
    coordenadas = data.get('coordenadas', [])

    if not id_ruta or not coordenadas:
        return jsonify({"success": False, "message": "Datos incompletos"})

    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            for punto in coordenadas:
                cursor.execute("""
                    INSERT INTO ruta_real_trazada (id_ruta, latitud, longitud)
                    VALUES (%s, %s, %s)
                """, (id_ruta, punto['lat'], punto['lng']))
        conexion.commit()
        return jsonify({"success": True})
    except Exception as e:
        print("Error al guardar trazado:", e)
        return jsonify({"success": False, "message": str(e)})



@app.route("/api/estado_ruta_actual", methods=["GET"])
def estado_ruta_actual():
    id_ruta = request.args.get("id_ruta")
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT estado_envio
                FROM asignacion_ruta_conductor
                WHERE id_ruta = %s
            """, (id_ruta,))
            estado = cursor.fetchone()
            if estado:
                return jsonify({"estado": estado[0]})
            else:
                return jsonify({"estado": None})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conexion.close()
    
# api_ruta.py

@app.route('/api/ubicaciones_ruta/<int:id_ruta>', methods=['GET'])
def obtener_ruta_real(id_ruta):
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT latitud, longitud 
                FROM ruta_real_trazada
                WHERE id_ruta = %s
                ORDER BY registrado_en ASC
            """, (id_ruta,))
            
            puntos = [{"lat": row[0], "lng": row[1]} for row in cursor.fetchall()]
        
        return jsonify({"success": True, "puntos": puntos})
    except Exception as e:
        print("❌ Error al obtener trazado:", e)
        return jsonify({"success": False, "message": str(e)})





@app.route('/api/rutas_programadas_hoy', methods=['GET'])
@jwt_required()
def api_rutas_programadas_hoy():
    try:
        rutas = controlador_rutas.obtener_rutas_programadas_hoy()
        return jsonify({"success": True, "rutas": rutas})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/ubicaciones_ruta", methods=["POST"])
def registrar_ubicacion_ruta():
    try:
        data = request.get_json()
        id_ruta = data.get("id_ruta")
        lat = data.get("lat")
        lon = data.get("lon")

        if not all([id_ruta, lat, lon]):
            return jsonify({"success": False, "message": "Faltan datos"}), 400

        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("""
                INSERT INTO ubicaciones_ruta (id_ruta, lat, lon)
                VALUES (%s, %s, %s)
            """, (id_ruta, lat, lon))
        conexion.commit()
        return jsonify({"success": True}), 200

    except Exception as e:
        print("❌ Error al registrar ubicación:", e)
        return jsonify({"success": False, "message": str(e)}), 500





@app.route("/api/marcar_ruta_activa", methods=["POST"])
def marcar_ruta_activa():
    try:
        data = request.get_json()
        id_ruta = data.get("id_ruta")

        if not id_ruta:
            return jsonify({"success": False, "message": "Falta el id_ruta"}), 400

        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("""
                UPDATE asignacion_ruta_conductor
                SET estado_envio = NULL
                WHERE estado_envio = 'vehiculo_iniciar';
            """)
            cursor.execute("""
                UPDATE asignacion_ruta_conductor
                SET estado_envio = 'vehiculo_iniciar'
                WHERE id_ruta = %s;
            """, (id_ruta,))

        conexion.commit()
        return jsonify({"success": True, "message": "Ruta lista para el SIM"}), 200

    except Exception as e:
        print("❌ Error al marcar ruta activa:", str(e))
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        conexion.close()
@app.route("/api/estado-ruta/<int:id_ruta>", methods=["GET"])
def verificar_estado_ruta(id_ruta):
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT estado
                FROM asignacion_ruta_conductor
                WHERE id_ruta = %s;
            """, (id_ruta,))
            
            resultado = cursor.fetchone()

            if resultado is None:
                return jsonify({"success": False, "message": "Ruta no encontrada"}), 404

            estado = resultado[0]

            if estado == 'finalizado':
                return jsonify({"success": True, "estado": "finalizado"}), 200
            else:
                return jsonify({"success": True, "estado": estado}), 200

    except Exception as e:
        print("❌ Error al verificar estado de ruta:", str(e))
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        conexion.close()


def obtener_direccion_desde_coordenadas(lat, lon):
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
        headers = {'User-Agent': 'sim808-tracker'}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            address = data.get("address", {})
            return address.get("suburb") or address.get("city") or address.get("town") or address.get("state") or f"Lat: {lat}, Lon: {lon}"
        else:
            return f"Lat: {lat}, Lon: {lon}"
    except Exception as e:
        print("❌ Error obteniendo dirección:", str(e))
        return f"Lat: {lat}, Lon: {lon}"


def formatear_rutas_hora_lima(rutas):
    lima = timezone("America/Lima")
    for r in rutas:
        if r.get("hora_salida"):
            r["hora_salida"] = r["hora_salida"].astimezone(lima)
    return rutas


@app.route("/api/registrar_origen_gps", methods=["POST"], strict_slashes=False)
def registrar_origen_gps():
    print(" Headers recibidos:")
    for key, value in request.headers.items():
        print(f"{key}: {value}")

    print("\nCuerpo crudo recibido (request.data):")
    print(request.data)

    try:
        raw = request.data.decode("utf-8").replace('\x1a', '')
        data = json.loads(raw)
    except Exception as e:
        print(" No se pudo procesar el JSON:", e)
        return jsonify({"error": "JSON inválido"}), 400

    print(" Payload recibido:", data)
    try:
        id_ruta = int(data.get("id_ruta"))
        lat = float(data.get("lat"))
        lon = float(data.get("lon"))
        hora_str = data.get("hora", "").strip()
        if not hora_str:
            return jsonify({"error": "Campo 'hora' es obligatorio"}), 400
        if len(hora_str) < 14:
            return jsonify({"error": "Formato de hora incompleto"}), 400

        hora_sim = datetime.strptime(hora_str[:14], "%Y%m%d%H%M%S")
        hora_utc = utc.localize(hora_sim)
        hora_lima = hora_utc.astimezone(timezone("America/Lima"))
    except Exception as e:
        print(" Error procesando datos:", e)
        return jsonify({"error": "Datos inválidos"}), 400
    try:
        direccion = obtener_direccion_desde_coordenadas(lat, lon)
        if not isinstance(direccion, str):
            direccion = str(direccion)
        direccion_corta = direccion.strip()[:100]  
        print(" Dirección geocodificada:", direccion_corta)

        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("""
                UPDATE rutas_programadas
                SET origen = %s,
                    origen_lat = %s,
                    origen_lon = %s,
                    hora_salida = %s
                WHERE id = %s;
            """, (direccion_corta, lat, lon, hora_lima, id_ruta))

            cursor.execute("""
                UPDATE asignacion_ruta_conductor
                SET estado_envio = 'vehiculo_iniciado'
                WHERE id_ruta = %s;
            """, (id_ruta,))

        conexion.commit()
        print(f"Origen y estado_envio actualizados para ruta {id_ruta}")
        return jsonify({
            "success": True,
            "message": "Origen actualizado correctamente",
            "hora_salida": hora_lima.isoformat()
        }), 200

    except Exception as e:
        conexion.rollback()
        print(" Error al actualizar en BD:", e)
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conexion.close()


        


@app.route("/api/registrar_ubicacion_gps", methods=["POST"])
def registrar_ubicacion_gps():
    try:
        raw = request.data.decode("utf-8").replace('\x1a', '')
        data = json.loads(raw)

        id_ruta = int(data.get("id_ruta"))
        lat = float(data.get("lat"))
        lon = float(data.get("lon"))
        hora_str = data.get("hora", "").strip()

        if not hora_str or len(hora_str) < 14:
            return jsonify({"success": False, "message": "Formato de hora inválido"}), 400

        hora_sim = datetime.strptime(hora_str[:14], "%Y%m%d%H%M%S")
        hora_utc = utc.localize(hora_sim)
        hora_lima = hora_utc.astimezone(timezone("America/Lima"))

        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("""
                INSERT INTO ubicaciones_ruta (id_ruta, lat, lon, hora)
                VALUES (%s, %s, %s, %s);
            """, (id_ruta, lat, lon, hora_lima))
        conexion.commit()

        return jsonify({"success": True, "message": "Ubicación registrada"}), 200

    except Exception as e:
        print("❌ Error al registrar ubicación:", e)
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/obtener_origen_ruta/<int:id_ruta>", methods=["GET"])
def obtener_origen_ruta(id_ruta):
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT origen_lat, origen_lon
                FROM rutas_programadas
                WHERE id = %s;
            """, (id_ruta,))
            fila = cursor.fetchone()
            if not fila:
                return jsonify({"success": False, "message": "No se encontró la ruta"}), 404

            lat, lon = fila

        return jsonify({"success": True, "lat": lat, "lon": lon}), 200

    except Exception as e:
        print("❌ Error al obtener origen desde rutas_programadas:", e)
        return jsonify({"success": False, "message": str(e)}), 500



    
    

@app.route("/api/finalizar_ruta", methods=["POST"])
def finalizar_ruta():
    try:
        data = request.get_json()
        id_ruta = data.get("id_ruta")
        hora_llegada = data.get("hora_llegada")  # 📲 Hora enviada desde frontend
        km_recorridos = data.get("km_recorridos")  # 📏 Km enviados desde frontend

        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("""
                UPDATE rutas_programadas
                SET hora_llegada = %s,
                    km_recorridos = %s
                WHERE id = %s;
            """, (hora_llegada, km_recorridos, id_ruta))

            cursor.execute("""
                UPDATE asignacion_ruta_conductor
                SET estado_envio = 'vehiculo_finalizado'
                WHERE id_ruta = %s;
            """, (id_ruta,))

        conexion.commit()
        return jsonify({"success": True, "message": "Ruta finalizada"}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conexion.close()

        
@app.route("/api/estado_ruta/<int:id_ruta>")
def estado_ruta(id_ruta):
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT estado_envio FROM asignacion_ruta_conductor
                WHERE id_ruta = %s;
            """, (id_ruta,))
            resultado = cursor.fetchone()
            if resultado:
                return jsonify({"estado_envio": resultado[0]})
            return jsonify({"estado_envio": None})
    finally:
        conexion.close()


@app.route("/api/ultima_ubicacion", methods=["GET"])
def obtener_ultima_ubicacion():
    try:
        id_ruta = int(request.args.get("id_ruta"))
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "id_ruta inválido"}), 400

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT lat, lon
                FROM ubicaciones_ruta
                WHERE id_ruta = %s
                ORDER BY hora DESC
                LIMIT 1;
            """, (id_ruta,))
            resultado = cursor.fetchone()
            if resultado:
                return jsonify({
                    "success": True,
                    "lat": resultado[0],
                    "lon": resultado[1]
                }), 200
            else:
                return jsonify({"success": False, "message": "No hay ubicaciones"}), 404
    except Exception as e:
        print("❌ Error al obtener ubicación:", e)
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conexion.close()


@app.route("/historial_rutas")
@jwt_required()
def historial_rutas():
    dni_usuario = get_jwt_identity()
    usuario = controlador_usuarios.obtener_usuario(dni_usuario)

    breadcrumbs = [
        {"name": "Inicio", "url": url_for("index")},
        {"name": "Historial de Rutas", "url": url_for("historial_rutas")}
    ]

    # =========================
    # 1) DATOS PARA LA TABLA
    # =========================
    # OJO: ajusta rp.destino al nombre real de tu columna de destino (texto)
    q_tabla = """
    SELECT
      rp.id AS id_ruta,

      NULLIF(TRIM(COALESCE(p.nombre,'') || ' ' || COALESCE(p.apellido,'')), '') AS conductor_raw,
      COALESCE(CONCAT(v.modelo, ' - ', v.placa), '')                             AS vehiculo_raw,

      -- Fecha/hora de ASIGNACIÓN como timestamp
      COALESCE(arc.fecha_asignacion, rp.fecha::timestamp)                         AS fecha_asignacion_ts,
      TO_CHAR(COALESCE(arc.fecha_asignacion, rp.fecha::timestamp),
              'YYYY-MM-DD HH24:MI')                                               AS fecha_asignacion_raw,

      -- Fecha/hora de LLEGADA: combinamos fecha + hora_llegada
      CASE
        WHEN rp.hora_llegada IS NOT NULL THEN
          (rp.fecha::timestamp + rp.hora_llegada)
        ELSE NULL
      END                                                                         AS fecha_llegada_ts,
      CASE
        WHEN rp.hora_llegada IS NOT NULL THEN
          TO_CHAR(rp.fecha::timestamp + rp.hora_llegada, 'YYYY-MM-DD HH24:MI')
        ELSE NULL
      END                                                                         AS fecha_llegada_raw,

      COALESCE(arc.estado, 'Activa')                                             AS estado_raw,

      -- DESTINO TEXTO (cambia rp.destino por tu campo real, si se llama distinto)
      rp.destino::text                                                           AS destino_raw,

      -- Minutos de recorrido = llegada_ts - asignacion_ts
      CASE
        WHEN rp.hora_llegada IS NOT NULL THEN
          EXTRACT(
            EPOCH FROM (
              (rp.fecha::timestamp + rp.hora_llegada)
              - COALESCE(arc.fecha_asignacion, rp.fecha::timestamp)
            )
          ) / 60
        ELSE NULL
      END                                                                         AS minutos_recorrido

    FROM rutas_programadas rp
    LEFT JOIN asignacion_ruta_conductor arc ON arc.id_ruta = rp.id
    LEFT JOIN personas p  ON p.id = arc.id_persona
    LEFT JOIN vehiculos v ON v.id = arc.id_vehiculo
    ORDER BY rp.fecha DESC, rp.id DESC;
    """

    # =========================
    # 2) MARCADORES (por si los usas luego)
    # =========================
    q_marcadores = """
    SELECT
      rp.id AS id_ruta,
      NULLIF(TRIM(COALESCE(p.nombre,'') || ' ' || COALESCE(p.apellido,'')), '')   AS conductor,
      COALESCE(v.modelo || ' - ' || v.placa, '')                                   AS vehiculo,
      COALESCE(arc.estado, 'Activa')                                               AS estado,
      TO_CHAR(COALESCE(arc.fecha_asignacion, rp.fecha), 'YYYY-MM-DD')              AS fecha,
      COALESCE(ur.lat, rp.origen_lat)                                              AS lat,
      COALESCE(ur.lon, rp.origen_lon)                                              AS lon
    FROM rutas_programadas rp
    LEFT JOIN asignacion_ruta_conductor arc ON arc.id_ruta = rp.id
    LEFT JOIN personas p  ON p.id = arc.id_persona
    LEFT JOIN vehiculos v ON v.id = arc.id_vehiculo
    LEFT JOIN LATERAL (
        SELECT lat, lon
        FROM ubicaciones_ruta u
        WHERE u.id_ruta = rp.id
        ORDER BY u.hora DESC
        LIMIT 1
    ) ur ON TRUE
    ORDER BY rp.fecha DESC, rp.id DESC;
    """

    # =========================
    # 3) RUTAS HISTÓRICAS (para azul/roja)
    # =========================
    # Ajusta rp.destino_lat / rp.destino_lon a tus nombres reales si los tienes
    q_rutas_historicas = """
    SELECT
      rp.id          AS id_ruta,
      rp.origen_lat  AS origen_lat,
      rp.origen_lon  AS origen_lon,
      rp.destino_lat AS destino_lat,
      rp.destino_lon AS destino_lon,
      u.lat          AS punto_lat,
      u.lon          AS punto_lon,
      u.hora         AS hora_punto
    FROM rutas_programadas rp
    LEFT JOIN ubicaciones_ruta u
      ON u.id_ruta = rp.id
    ORDER BY rp.id, u.hora;
    """

    con = obtener_conexion()
    cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # ---------- Tabla ----------
    cur.execute(q_tabla)
    rows = cur.fetchall()
    recorridos = []

    for r in rows:
        # Tiempo recorrido
        minutos = r["minutos_recorrido"]
        if minutos is None:
            tiempo_str = "—"
        else:
            minutos = int(round(minutos))
            if minutos < 60:
                tiempo_str = f"{minutos} min"
            else:
                h = minutos // 60
                m = minutos % 60
                tiempo_str = f"{h} h {m} min" if m else f"{h} h"

        # Fechas (ya vienen como texto en formato bonito)
        fecha_asig_str = r["fecha_asignacion_raw"] or ""
        fecha_lleg_str = r["fecha_llegada_raw"] or ""

        recorridos.append({
            "id_ruta":          r["id_ruta"],
            "conductor":        r["conductor_raw"] or "Sin asignar",
            "vehiculo":         r["vehiculo_raw"] or "Sin asignar",
            "fecha_asignacion": fecha_asig_str,
            "fecha_llegada":    fecha_lleg_str,
            "estado":           r["estado_raw"] or "Activa",
            "destino":          r["destino_raw"] or "",
            "tiempo_recorrido": tiempo_str,
        })

    # ---------- Marcadores ----------
    cur.execute(q_marcadores)
    conductor_markers = cur.fetchall()

    # ---------- Rutas históricas ----------
    cur.execute(q_rutas_historicas)
    puntos = cur.fetchall()

    rutas_dict = {}
    for p in puntos:
        rid = p["id_ruta"]
        if rid not in rutas_dict:
            rutas_dict[rid] = {
                "id_ruta": rid,
                "origen": {
                    "lat": float(p["origen_lat"]) if p["origen_lat"] is not None else None,
                    "lng": float(p["origen_lon"]) if p["origen_lon"] is not None else None,
                },
                "destino": {
                    "lat": float(p["destino_lat"]) if p["destino_lat"] is not None else None,
                    "lng": float(p["destino_lon"]) if p["destino_lon"] is not None else None,
                },
                "real": []  # trayecto real (puntos rojos)
            }

        if p["punto_lat"] is not None and p["punto_lon"] is not None:
            rutas_dict[rid]["real"].append({
                "lat": float(p["punto_lat"]),
                "lng": float(p["punto_lon"]),
            })

    # Si no hay destino_lat/lon pero sí puntos, usamos el último punto como destino
    for rid, data in rutas_dict.items():
        if (data["destino"]["lat"] is None or data["destino"]["lng"] is None) and data["real"]:
            last = data["real"][-1]
            data["destino"]["lat"] = last["lat"]
            data["destino"]["lng"] = last["lng"]

    rutas_historicas = list(rutas_dict.values())

    cur.close()
    con.close()

    return render_template(
        "historial_rutas.html",
        usuario=usuario,
        breadcrumbs=breadcrumbs,
        recorridos=recorridos,
        conductor_markers=conductor_markers,  # por si luego lo usas
        rutas_historicas=rutas_historicas     # 🔵🔴 para el mapa
    )


# ========== VISTA ==========
@app.route("/mantenimiento")
@jwt_required()
def mantenimiento():
    dni_usuario = get_jwt_identity()
    usuario = controlador_usuarios.obtener_usuario(dni_usuario)

    breadcrumbs = [
        {"name": "Inicio", "url": url_for("index")},
        {"name": "Mantenimiento de Vehículos", "url": url_for("mantenimiento")}
    ]

    # Para el selector de vehículo en la vista
    vehiculos = cm.obtener_vehiculos_min()

    return render_template(
        "mantenimiento.html",
        usuario=usuario,
        breadcrumbs=breadcrumbs,
        vehiculos=vehiculos
    )

# ========== API UI (carga por vehículo) ==========
@app.route("/api/mantenimiento/<int:vehiculo_id>/ui")
@jwt_required()
def api_mantenimiento_ui(vehiculo_id):
    # Dispara alertas antes de devolver (opcional)
    cm.disparar_alertas_preventivas(vehiculo_id)
    cm.disparar_alertas_predictivas(vehiculo_id)

    data = {
    "cabecera": cm.obtener_cabecera_calculos(vehiculo_id),
    "alertas_conf": cm.obtener_alertas_conf(vehiculo_id),
    "combustible": cm.obtener_cargas_combustible(vehiculo_id),
    "por_horas": cm.obtener_por_horas(vehiculo_id),  # ← devolverá []
    "por_km": cm.obtener_por_km(vehiculo_id),
    "por_tiempo": cm.obtener_por_tiempo(vehiculo_id),
    "alertas_activas": cm.obtener_alertas_activas(vehiculo_id)
}

    return jsonify({"ok": True, "data": data})

# ========== API: crear/cerrar OT ==========
@app.route("/api/mantenimiento/ot", methods=["POST"])
@jwt_required()
def api_crear_ot():
    j = request.get_json() or {}
    vehiculo_id = int(j.get("vehiculo_id"))
    nro_ot = str(j.get("nro_ot"))
    niveles = j.get("niveles")  # ej. "2, 1"
    ot_id = cm.crear_ot(vehiculo_id, nro_ot, niveles)
    return jsonify({"ok": True, "ot_id": ot_id})

@app.route("/api/mantenimiento/ot/<int:ot_id>/cerrar", methods=["POST"])
@jwt_required()
def api_cerrar_ot(ot_id):
    cm.cerrar_ot(ot_id)
    return jsonify({"ok": True})

@app.route("/api/sensores/push", methods=["POST"])
def api_push_sensor():
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        pass
    j = request.get_json(silent=True) or request.form or {}
    try:
        app.logger.debug("api_push_sensor payload: %s", j)

        vehiculo_id = int(j.get("vehiculo_id"))
        clave = str(j.get("clave"))             # p.ej. "vibracion_motor"
        valor = float(j.get("valor"))
    except Exception as e:
        app.logger.exception("Payload inválido en api_push_sensor: %s", e)
        return jsonify({"ok": False, "error": "Payload inválido"}), 400

    try:
        cm.insertar_lectura_sensor(vehiculo_id, clave, valor)
        # Opcional: disparar predictivo al vuelo
        cm.disparar_alertas_predictivas(vehiculo_id)
        return jsonify({"ok": True})
    except Exception as e:
        app.logger.exception("Error insertando lectura sensor: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500

# ========== API: forzar disparo de alertas ==========
@app.route("/api/mantenimiento/<int:vehiculo_id>/alertas/disparar", methods=["POST"])
@jwt_required()
def api_disparar_alertas(vehiculo_id):
    cm.disparar_alertas_preventivas(vehiculo_id)
    cm.disparar_alertas_predictivas(vehiculo_id)
    return jsonify({"ok": True})

ROL_ADMIN_ID = 1  # Administrador
ROL_CONDUCTOR_ID = 2  # ← ajusta si tu rol de conductor es otro

def obtener_conductores():
    """Devuelve personas activas con rol de conductor."""
    con = obtener_conexion()
    try:
        with con.cursor() as cur:
            cur.execute("""
                SELECT id, nombre, apellido, dni
                FROM personas
                WHERE COALESCE(estado, TRUE) = TRUE
                  AND COALESCE(eliminado, FALSE) = FALSE
                  AND id_rol = %s
                ORDER BY nombre, apellido
            """, (ROL_CONDUCTOR_ID,))
            rows = cur.fetchall()
            # convierte a diccionarios simples
            conductores = [
                {"id": r[0], "nombre": r[1], "apellido": r[2], "dni": r[3]}
                for r in rows
            ]
            return conductores
    finally:
        con.close()


@app.route("/registro_temperatura_humedad")
def registro_temperatura_humedad():
    try:
        verify_jwt_in_request(optional=True)
        dni_usuario = get_jwt_identity()
    except Exception:
        dni_usuario = None

    if not dni_usuario:
        dni_usuario = session.get('dni_usuario')

    usuario = controlador_usuarios.obtener_usuario(dni_usuario) if dni_usuario else None
    puede_registrar = bool(usuario and int(usuario.get('rol_id') or 0) == ROL_ADMIN_ID)

    breadcrumbs = [
        {"name": "Inicio", "url": url_for("index")},
        {"name": "Registro temp. y humedad", "url": url_for("registro_temperatura_humedad")}
    ]

    # Vehículos activos
    try:
        vehiculos_all = obtener_vehiculos()
        vehiculos_activos = []
        for v in vehiculos_all:
            if isinstance(v, dict):
                estado = v.get('estado', v.get('activo'))
                if estado in (True, 'activo', 1, '1', 't', 'true') or estado is None:
                    vehiculos_activos.append(v)
            else:
                vehiculos_activos.append(v)
    except Exception as e:
        vehiculos_activos = []
        app.logger.exception("Error obteniendo vehículos: %s", e)

    # Conductores (personas con rol conductor)
    try:
        conductores = obtener_conductores()
    except Exception as e:
        app.logger.exception("Error obteniendo conductores: %s", e)
        conductores = []

    return render_template(
        "registro_temperatura_humedad.html",
        usuario=usuario,
        breadcrumbs=breadcrumbs,
        vehiculos=vehiculos_activos,
        conductores=conductores,          # ← PASAMOS CONDUCTORES
        puede_registrar=puede_registrar
    )


bp_umbrales = Blueprint('umbrales', __name__)

def _get_usuario_actual():
    """Obtiene el usuario (DictRow) usando JWT o sesión."""
    try:
        verify_jwt_in_request(optional=True)
        dni_usuario = get_jwt_identity()
    except Exception:
        dni_usuario = None
    if not dni_usuario:
        dni_usuario = session.get('dni_usuario')

    # Import tardío para evitar ciclos
    return controlador_usuarios.obtener_usuario(dni_usuario) if dni_usuario else None


@app.route("/api/sensores/umbrales/guardar", methods=["POST"])
def api_guardar_umbrales():
    data = request.get_json(force=True)

    aplicar_todos = bool(data.get('aplicar_todos'))
    vehiculo_id   = data.get('vehiculo_id')
    temp_min      = data.get('temp_min')
    temp_max      = data.get('temp_max')
    rh_min        = data.get('rh_min')
    rh_max        = data.get('rh_max')

    # Validaciones
    for k in ('temp_min','temp_max','rh_min','rh_max'):
        if data.get(k) is None:
            return jsonify({"message": f"Campo {k} es obligatorio"}), 400
    try:
        tmin = float(temp_min); tmax = float(temp_max)
        hmin = float(rh_min);   hmax = float(rh_max)
    except Exception:
        return jsonify({"message": "Valores numéricos inválidos"}), 400
    if tmin >= tmax: return jsonify({"message":"Temp Min debe ser < Temp Max"}), 400
    if hmin >= hmax: return jsonify({"message":"RH Min debe ser < RH Max"}), 400

    # Usuario / solo Admin
    try:
        verify_jwt_in_request(optional=True); dni_usuario = get_jwt_identity()
    except Exception:
        dni_usuario = None
    if not dni_usuario:
        dni_usuario = session.get('dni_usuario')

    usuario = controlador_usuarios.obtener_usuario(dni_usuario) if dni_usuario else None
    if not usuario:
        return jsonify({"message":"Sesión no válida"}), 401
    if int(usuario.get('rol_id') or 0) != ROL_ADMIN_ID:
        return jsonify({"message":"Solo el Administrador puede registrar umbrales"}), 403

    persona_id = usuario.get('persona_id')
    if not persona_id:
        return jsonify({"message":"No se encontró persona asociada"}), 400

    con = obtener_conexion()
    try:
        with con.cursor() as cur:
            # ===== CORRECCIÓN AQUÍ =====
            if aplicar_todos:
                cur.execute("""
                    SELECT id
                    FROM vehiculos
                    WHERE COALESCE(estado, TRUE) = TRUE
                """)
                ids = [r[0] for r in cur.fetchall()]
                if not ids:
                    return jsonify({"message":"No hay vehículos activos para aplicar"}), 400
            else:
                if not vehiculo_id:
                    return jsonify({"message":"vehiculo_id requerido cuando no es masivo"}), 400
                ids = [int(vehiculo_id)]
            # ===========================

            # Upsert sin ON CONFLICT
            upd_sql = """
                UPDATE sensores_umbrales
                   SET temp_min = %s,
                       temp_max = %s,
                       rh_min   = %s,
                       rh_max   = %s,
                       persona_id = %s,
                       actualizado_en = NOW()
                 WHERE vehiculo_id = %s
            """
            ins_sql = """
                INSERT INTO sensores_umbrales
                    (vehiculo_id, temp_min, temp_max, rh_min, rh_max, persona_id, actualizado_en)
                VALUES
                    (%s, %s, %s, %s, %s, %s, NOW())
            """
            afectados = 0
            for vid in ids:
                cur.execute(upd_sql, (tmin, tmax, hmin, hmax, persona_id, vid))
                if cur.rowcount == 0:
                    cur.execute(ins_sql, (vid, tmin, tmax, hmin, hmax, persona_id))
                afectados += 1

        con.commit()
        return jsonify({"message":"Umbrales guardados correctamente", "vehiculos_afectados": afectados}), 200

    except Exception as e:
        con.rollback()
        return jsonify({"message":"Error al guardar umbrales", "detail": str(e)}), 500
    finally:
        con.close()

# === LEER UMBRALES POR VEHÍCULO (GET) ===

@app.route("/api/sensores/umbrales/<int:vehiculo_id>", methods=["GET"])
def api_obtener_umbrales_por_id(vehiculo_id: int):
    """
    Devuelve los umbrales guardados para un vehículo.
    Respuesta:
      200: {"umbrales": {"vehiculo_id": X, "temp_min": ..., "temp_max": ..., "rh_min": ..., "rh_max": ...}}
      404: {"message": "No hay umbrales para este vehículo"}
    """
    con = obtener_conexion()
    try:
        with con.cursor() as cur:
            cur.execute("""
                SELECT temp_min, temp_max, rh_min, rh_max
                FROM sensores_umbrales
                WHERE vehiculo_id = %s
                LIMIT 1
            """, (vehiculo_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"message": "No hay umbrales para este vehículo"}), 404

            # row por posición porque usamos SELECT explícito en orden conocido
            umbrales = {
                "vehiculo_id": vehiculo_id,
                "temp_min": float(row[0]),
                "temp_max": float(row[1]),
                "rh_min":   float(row[2]),
                "rh_max":   float(row[3]),
            }
            return jsonify({"umbrales": umbrales}), 200
    except Exception as e:
        app.logger.exception("Error al obtener umbrales")
        return jsonify({"message": "Error al obtener umbrales", "detail": str(e)}), 500
    finally:
        con.close()


# Ruta alternativa por compatibilidad con el frontend (mismo resultado)
@app.route("/api/sensores/umbrales/vehiculo/<int:vehiculo_id>", methods=["GET"])
def api_obtener_umbrales_por_id_alt(vehiculo_id: int):
    return api_obtener_umbrales_por_id(vehiculo_id)




if __name__ == "__main__":
          app.run(host="0.0.0.0", port=8000, debug=True)