from flask import Flask, render_template, request, redirect, flash, make_response, url_for, jsonify
from flask_jwt_extended import JWTManager, create_access_token, set_access_cookies, unset_jwt_cookies, jwt_required, get_jwt_identity, exceptions
import hashlib
import os
from datetime import timedelta
import json
import controladores.controlador_usuarios as controlador_usuarios

app = Flask(__name__, static_url_path='/static', static_folder='static')
from flask_jwt_extended import JWTManager
app.secret_key = 'super-secret'
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_COOKIE_SECURE'] = False  # Pon True si usas HTTPS
app.config['JWT_ACCESS_COOKIE_NAME'] = 'access_token_cookie'
app.config['JWT_COOKIE_CSRF_PROTECT'] = False  # Pon True si usarás CSRF con cookies

jwt = JWTManager(app)


# Ruta para la página de inicio de sesión
@app.route("/")
@app.route("/login_user")
def login():
    resp = make_response(render_template("login_user.html"))
    unset_jwt_cookies(resp)  # Limpia las cookies previas
    return resp

# Procesar inicio de sesión
@app.route("/procesar_login", methods=["POST"])
def procesar_login():
    try:
        dni_usuario = request.form["dni_usuario"].strip()
        password = request.form["password"].strip()

        usuario = controlador_usuarios.obtener_usuario(dni_usuario)
        if not usuario:
            flash("Usuario no encontrado.")
            return redirect("/login_user")

        h = hashlib.new("sha256")
        h.update(password.encode("utf-8"))
        encpass = h.hexdigest().lower()

        if encpass == usuario[2].lower():  # usuario[2] es el campo `pass`
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

# Procesar cierre de sesión
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






if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)