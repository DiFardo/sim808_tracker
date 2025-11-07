from bd_conexion import obtener_conexion
# controladores/controlador_mantenimiento.py

# Utilidad: convierte filas (tu cursor por defecto) a dict sencillo
def _rows_to_dicts(cols, rows):
    return [dict(zip(cols, r)) for r in rows]


# ==== helpers num/fecha para serializar ====
from datetime import date, datetime
from decimal import Decimal

def _to_num(x):
    if x is None: return None
    if isinstance(x, Decimal): return float(x)
    try:
        return float(x)
    except Exception:
        return None

def _to_iso(x):
    if x is None: return None
    if isinstance(x, (datetime, date)): return x.isoformat()
    return str(x)

def obtener_cabecera_calculos(vehiculo_id:int):
    sql = """
    WITH ultima_ot AS (
      SELECT DISTINCT ON (id_vehiculo)
             id_vehiculo, id, nro_ot, fecha_inicio, niveles,
             COALESCE(km_inicio,0) AS km_inicio
      FROM mp_orden_trabajo
      WHERE id_vehiculo = %s
      ORDER BY id_vehiculo, fecha_inicio DESC
    )
    SELECT v.id AS vehiculo_id, v.placa, v.modelo,
           uo.nro_ot, uo.fecha_inicio AS fecha_inicio_tareas, uo.niveles,
           uo.km_inicio,
           COALESCE(v.odometro,0)  AS odometro,
           -- progresos (solo KM)
           (COALESCE(v.odometro,0) - COALESCE(uo.km_inicio,0)) AS km_realizados
    FROM vehiculos v
    LEFT JOIN ultima_ot uo ON uo.id_vehiculo = v.id
    WHERE v.id = %s
    """
    con = obtener_conexion(); cur = con.cursor()
    cur.execute(sql, (vehiculo_id, vehiculo_id))
    row = cur.fetchone()
    cur.close(); con.close()
    if not row:
        return {}
    (vehiculo_id, placa, modelo,
     nro_ot, fecha_inicio_tareas, niveles,
     km_inicio, odometro, km_realizados) = row
    return {
        "vehiculo_id": vehiculo_id,
        "placa": placa,
        "modelo": modelo,
        "nro_ot": nro_ot,
        "fecha_inicio_tareas": _to_iso(fecha_inicio_tareas),
        "niveles": niveles,
        "km_inicio": _to_num(km_inicio),
        "odometro": _to_num(odometro),
        "km_realizados": _to_num(km_realizados),
    }


def obtener_por_km(vehiculo_id:int):
    sql = """
    WITH ot AS (
      SELECT *
      FROM mp_orden_trabajo
      WHERE id_vehiculo = %s
      ORDER BY fecha_inicio DESC
      LIMIT 1
    ),
    v AS (
      -- ⚠️ Aseguramos siempre un número finito
      SELECT id, COALESCE(odometro,0) AS odometro
      FROM vehiculos
      WHERE id = %s
    ),
    i AS (
      SELECT nivel, valor_objetivo
      FROM mp_intervalo
      WHERE id_vehiculo = %s AND activo IS TRUE AND tipo = 'KM'
    )
    SELECT
      i.nivel,
      i.valor_objetivo,
      -- ✅ Siempre numérico y ≥ 0
      GREATEST(COALESCE(v.odometro,0) - COALESCE(ot.km_inicio,0), 0)::numeric(12,1)                          AS km_realizados,
      -- ✅ También casteado para evitar NaN al serializar
      (i.valor_objetivo - GREATEST(COALESCE(v.odometro,0) - COALESCE(ot.km_inicio,0), 0))::numeric(12,1)     AS km_faltantes,
      CASE
        WHEN ot.fecha_inicio IS NULL THEN NULL
        ELSE ROUND(
          (COALESCE(v.odometro,0) - COALESCE(ot.km_inicio,0)) /
          NULLIF(EXTRACT(EPOCH FROM (NOW() - ot.fecha_inicio)) / 86400.0, 0)
      , 1)
      END AS promedio_diario,
      CASE
        WHEN ot.fecha_inicio IS NULL THEN NULL
        WHEN (COALESCE(v.odometro,0) - COALESCE(ot.km_inicio,0)) <= 0 THEN NULL
        ELSE
          ot.fecha_inicio
          + (i.valor_objetivo /
             NULLIF(
               (COALESCE(v.odometro,0) - COALESCE(ot.km_inicio,0)) /
               NULLIF(EXTRACT(EPOCH FROM (NOW() - ot.fecha_inicio)) / 86400.0, 0)
             , 0)
            ) * INTERVAL '1 day'
      END AS fecha_estimada
    FROM i, v
    LEFT JOIN ot ON TRUE
    ORDER BY i.nivel
    """
    con = obtener_conexion(); cur = con.cursor()
    cur.execute(sql, (vehiculo_id, vehiculo_id, vehiculo_id))
    rows = cur.fetchall()
    cur.close(); con.close()
    out = []
    for (nivel, valor_obj, km_real, km_falt, prom, f_est) in rows:
        out.append({
            "nivel": nivel,
            "km_realizados": _to_num(km_real),
            "km_faltantes": _to_num(km_falt),
            "promedio_diario": _to_num(prom),
            "fecha_estimada": _to_iso(f_est),
        })
    return out


# ====== POR HORAS ======
def obtener_por_horas(vehiculo_id:int):
    sql = """
    WITH ot AS (
      SELECT *
      FROM mp_orden_trabajo
      WHERE id_vehiculo = %s
      ORDER BY fecha_inicio DESC
      LIMIT 1
    ),
    v AS (
      SELECT id, horometro
      FROM vehiculos
      WHERE id = %s
    ),
    i AS (
      SELECT nivel, valor_objetivo
      FROM mp_intervalo
      WHERE id_vehiculo = %s AND activo IS TRUE AND tipo = 'HORAS'
    )
    SELECT
      i.nivel,
      i.valor_objetivo,
      GREATEST(v.horometro - COALESCE(ot.horas_inicio, 0), 0)::numeric(12,1)    AS horas_realizadas,
      (i.valor_objetivo - GREATEST(v.horometro - COALESCE(ot.horas_inicio,0),0)) AS horas_faltantes,
      CASE
        WHEN ot.fecha_inicio IS NULL THEN NULL
        ELSE ROUND(
          (v.horometro - COALESCE(ot.horas_inicio,0)) /
          NULLIF(EXTRACT(EPOCH FROM (NOW() - ot.fecha_inicio))/86400.0, 0)
        ,1)
      END AS promedio_diario,
      CASE
        WHEN ot.fecha_inicio IS NULL THEN NULL
        WHEN (v.horometro - COALESCE(ot.horas_inicio,0)) <= 0 THEN NULL
        ELSE
          ot.fecha_inicio
          + ((i.valor_objetivo) /
             NULLIF(
               (v.horometro - COALESCE(ot.horas_inicio,0)) /
               NULLIF(EXTRACT(EPOCH FROM (NOW() - ot.fecha_inicio))/86400.0, 0)
             , 0)
            ) * INTERVAL '1 day'
      END AS fecha_estimada,
      v.horometro AS horometro
    FROM i, v
    LEFT JOIN ot ON TRUE
    ORDER BY i.nivel
    """
    con = obtener_conexion(); cur = con.cursor()
    cur.execute(sql, (vehiculo_id, vehiculo_id, vehiculo_id))
    rows = cur.fetchall()
    cur.close(); con.close()
    out = []
    for (nivel, valor_obj, hrs_real, hrs_falt, prom, f_est, horometro) in rows:
        out.append({
            "nivel": nivel,
            "horas_realizadas": _to_num(hrs_real),
            "horas_faltantes": _to_num(hrs_falt),
            "promedio_diario": _to_num(prom),
            "fecha_estimada": _to_iso(f_est),
            "horometro": _to_num(horometro),
        })
    return out

# ====== POR TIEMPO ======
def obtener_por_tiempo(vehiculo_id:int):
    sql = """
    WITH ot AS (
      SELECT *
      FROM mp_orden_trabajo
      WHERE id_vehiculo = %s
      ORDER BY fecha_inicio DESC
      LIMIT 1
    ),
    i AS (
      SELECT nivel, valor_objetivo
      FROM mp_intervalo
      WHERE id_vehiculo = %s AND activo IS TRUE AND tipo = 'TIEMPO'
    )
    SELECT
      i.nivel,
      i.valor_objetivo,
      ot.fecha_inicio::date                                  AS fecha_inicio,
      (ot.fecha_inicio::date + (i.valor_objetivo || ' days')::interval)::date AS fecha_estimada,
      (i.valor_objetivo - GREATEST((CURRENT_DATE - ot.fecha_inicio::date), 0))::int AS faltan_dias,
      CASE
        WHEN CURRENT_DATE >= (ot.fecha_inicio::date + (i.valor_objetivo || ' days')::interval)::date THEN 'VENCIDO'
        ELSE 'EN CURSO'
      END AS estado
    FROM i
    LEFT JOIN ot ON TRUE
    ORDER BY i.nivel
    """
    con = obtener_conexion(); cur = con.cursor()
    cur.execute(sql, (vehiculo_id, vehiculo_id))
    rows = cur.fetchall()
    cur.close(); con.close()
    out = []
    for (nivel, valor_obj, f_ini, f_est, faltan, estado) in rows:
        out.append({
            "nivel": nivel,
            "fecha_inicio": _to_iso(f_ini),
            "fecha_estimada": _to_iso(f_est),
            "faltan_dias": int(faltan) if faltan is not None else None,
            "estado": estado,
        })
    return out



# --- UPSERT de alertas de vencimiento por vehículo ---
def guardar_alertas_conf(vehiculo_id:int, seguro_venc, tecnica_venc, ruta_venc, matafuego_venc):
    from bd_conexion import obtener_conexion
    con = obtener_conexion(); cur = con.cursor()
    cur.execute("""
      INSERT INTO vehiculo_alertas_conf
        (id_vehiculo, seguro_venc, tecnica_venc, ruta_venc, matafuego_venc, estado)
      VALUES (%s, %s, %s, %s, %s, TRUE)
      ON CONFLICT (id_vehiculo) DO UPDATE SET
        seguro_venc = EXCLUDED.seguro_venc,
        tecnica_venc = EXCLUDED.tecnica_venc,
        ruta_venc    = EXCLUDED.ruta_venc,
        matafuego_venc = EXCLUDED.matafuego_venc,
        estado = TRUE
    """, (vehiculo_id, seguro_venc, tecnica_venc, ruta_venc, matafuego_venc))
    con.commit()
    cur.close(); con.close()
    return True


def obtener_vehiculos_min():
    sql = """
    SELECT id, placa, modelo, marca, anio, estado, imagen,
           COALESCE(odometro,0) AS odometro
    FROM vehiculos
    WHERE estado = TRUE
    ORDER BY placa;
    """
    con = obtener_conexion(); cur = con.cursor()
    cur.execute(sql); rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    data = _rows_to_dicts(cols, rows)
    cur.close(); con.close()
    return data


# ====== PANELES LATERALES ======
def obtener_alertas_conf(vehiculo_id:int):
    sql = """
    SELECT seguro_venc, tecnica_venc, ruta_venc, matafuego_venc
    FROM vehiculo_alertas_conf
    WHERE id_vehiculo = %s
    """
    con = obtener_conexion(); cur = con.cursor()
    cur.execute(sql, (vehiculo_id,))
    row = cur.fetchone()
    cur.close(); con.close()
    if not row: return {"seguro_venc":None,"tecnica_venc":None,"ruta_venc":None,"matafuego_venc":None}
    return {"seguro_venc":row[0], "tecnica_venc":row[1], "ruta_venc":row[2], "matafuego_venc":row[3]}

def obtener_cargas_combustible(vehiculo_id:int, limite:int=50):
    sql = """
    SELECT id, fecha, categoria AS catcon, chofer, litros, precio, km_inicio
    FROM vehiculo_combustible
    WHERE id_vehiculo = %s
    ORDER BY fecha DESC
    LIMIT %s
    """
    con = obtener_conexion(); cur = con.cursor()
    cur.execute(sql, (vehiculo_id, limite))
    rows = cur.fetchall(); cols = [d[0] for d in cur.description]
    data = _rows_to_dicts(cols, rows)
    cur.close(); con.close()
    return data




# ====== ALERTAS ACTIVAS (unificado) ======
def obtener_alertas_activas(vehiculo_id:int, limite:int=20):
    sql = """
    SELECT id, origen, tipo, detalle, severidad, ts
    FROM vehiculo_alerta
    WHERE id_vehiculo = %s AND atendida = FALSE
    ORDER BY ts DESC
    LIMIT %s
    """
    con = obtener_conexion(); cur = con.cursor()
    cur.execute(sql, (vehiculo_id, limite))
    rows = cur.fetchall(); cols = [d[0] for d in cur.description]
    data = _rows_to_dicts(cols, rows)
    cur.close(); con.close()
    return data

# ====== DISPARADORES DE ALERTAS ======
def disparar_alertas_predictivas(vehiculo_id:int):
    sql = """
    INSERT INTO vehiculo_alerta (id_vehiculo, origen, tipo, detalle, severidad, ts)
    SELECT s.id_vehiculo,
           'PREDICTIVO',
           'Umbral '||u.clave,
           'Valor='||s.valor||' '||u.operador||' '||u.limite,
           u.severidad,
           s.ts
    FROM sensor_lectura s
    JOIN sensor_umbral u
      ON u.id_vehiculo = s.id_vehiculo
     AND u.clave = s.clave
     AND u.activo = TRUE
    WHERE s.id_vehiculo = %s
      AND s.ts >= now() - interval '5 minutes'
      AND (
            (u.operador = '>'  AND s.valor >  u.limite) OR
            (u.operador = '>=' AND s.valor >= u.limite) OR
            (u.operador = '<'  AND s.valor <  u.limite) OR
            (u.operador = '<=' AND s.valor <= u.limite)
          )
      AND NOT EXISTS (
        SELECT 1 FROM vehiculo_alerta a
        WHERE a.id_vehiculo = s.id_vehiculo
          AND a.origen = 'PREDICTIVO'
          AND a.tipo = 'Umbral '||u.clave
          AND a.ts >= now() - interval '10 minutes'
      );
    """
    con = obtener_conexion(); cur = con.cursor()
    cur.execute(sql, (vehiculo_id,))
    con.commit()
    cur.close(); con.close()
    return True

def disparar_alertas_preventivas(vehiculo_id:int):
    sql = """
    INSERT INTO vehiculo_alerta (id_vehiculo, origen, tipo, detalle, severidad, ts)
    SELECT v.id_vehiculo, 'PREVENTIVO', v.tipo, v.detalle, v.severidad, now()
    FROM (
      SELECT id_vehiculo, 'Seguro vencido' AS tipo,
             'Fecha vencimiento: '||seguro_venc AS detalle,
             CASE WHEN seguro_venc <= current_date THEN 3
                  WHEN seguro_venc <= current_date + 15 THEN 2
                  ELSE 1 END AS severidad,
             seguro_venc AS f
      FROM vehiculo_alertas_conf WHERE estado AND id_vehiculo = %s

      UNION ALL
      SELECT id_vehiculo, 'Técnica por vencer',
             'Vence el '||tecnica_venc,
             CASE WHEN tecnica_venc <= current_date THEN 3
                  WHEN tecnica_venc <= current_date + 15 THEN 2
                  ELSE 1 END,
             tecnica_venc
      FROM vehiculo_alertas_conf WHERE estado AND id_vehiculo = %s

      UNION ALL
      SELECT id_vehiculo, 'Ruta por vencer',
             'Vence el '||ruta_venc,
             CASE WHEN ruta_venc <= current_date THEN 3
                  WHEN ruta_venc <= current_date + 15 THEN 2
                  ELSE 1 END,
             ruta_venc
      FROM vehiculo_alertas_conf WHERE estado AND id_vehiculo = %s

      UNION ALL
      SELECT id_vehiculo, 'Matafuego por vencer',
             'Vence el '||matafuego_venc,
             CASE WHEN matafuego_venc <= current_date THEN 3
                  WHEN matafuego_venc <= current_date + 15 THEN 2
                  ELSE 1 END,
             matafuego_venc
      FROM vehiculo_alertas_conf WHERE estado AND id_vehiculo = %s
    ) v
    WHERE v.f IS NOT NULL
      AND v.f <= current_date + 15
      AND NOT EXISTS (
        SELECT 1 FROM vehiculo_alerta a
        WHERE a.id_vehiculo = v.id_vehiculo
          AND a.origen = 'PREVENTIVO'
          AND a.tipo = v.tipo
          AND a.ts::date = current_date
      );
    """
    con = obtener_conexion(); cur = con.cursor()
    cur.execute(sql, (vehiculo_id, vehiculo_id, vehiculo_id, vehiculo_id))
    con.commit()
    cur.close(); con.close()
    return True

def crear_ot(vehiculo_id:int, nro_ot:str, niveles:str=None):
    sql = """
    INSERT INTO mp_orden_trabajo (id_vehiculo, nro_ot, niveles, horas_inicio, km_inicio, estado)
    SELECT v.id, %s, %s, 0, COALESCE(v.odometro,0), 'ABIERTA'
    FROM vehiculos v WHERE v.id = %s
    RETURNING id;
    """
    con = obtener_conexion(); cur = con.cursor()
    cur.execute(sql, (nro_ot, niveles, vehiculo_id))
    ot_id = cur.fetchone()[0]
    con.commit(); cur.close(); con.close()
    return ot_id


def cerrar_ot(ot_id:int):
    con = obtener_conexion(); cur = con.cursor()
    cur.execute("UPDATE mp_orden_trabajo SET estado='CERRADA' WHERE id=%s", (ot_id,))
    con.commit(); cur.close(); con.close()
    return True

# ====== Sensores (push) ======
def insertar_lectura_sensor(vehiculo_id:int, clave:str, valor:float):
    con = obtener_conexion(); cur = con.cursor()
    cur.execute(
        "INSERT INTO sensor_lectura (id_vehiculo, clave, valor) VALUES (%s,%s,%s)",
        (vehiculo_id, clave, valor)
    )
    con.commit(); cur.close(); con.close()
    return True
