"""database.py - Capa de datos (SQLite). Todas las consultas del proyecto viven aquí."""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta

import config
from reloj import ahora

FMT = "%Y-%m-%d %H:%M:%S"


def ts(dt=None):
    return (dt or ahora()).strftime(FMT)


def a_dt(texto):
    return datetime.strptime(texto, FMT)


SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    telefono TEXT PRIMARY KEY, nombre TEXT, creado TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS sesiones (
    telefono TEXT PRIMARY KEY, estado TEXT, datos TEXT, actualizado TEXT);

CREATE TABLE IF NOT EXISTS medicamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telefono TEXT NOT NULL, nombre TEXT NOT NULL, dosis TEXT,
    horas TEXT NOT NULL,                 -- "08:00,16:00"
    fecha_inicio TEXT NOT NULL, fecha_fin TEXT,   -- fecha_fin NULL = tratamiento continuo
    activo INTEGER NOT NULL DEFAULT 1, creado TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS tomas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    med_id INTEGER NOT NULL REFERENCES medicamentos(id) ON DELETE CASCADE,
    fecha TEXT NOT NULL, hora TEXT NOT NULL,
    estado TEXT NOT NULL,   -- enviado | pospuesta | tomada | omitida | perdida | cancelada
    recordar_en TEXT, enviado_en TEXT,
    UNIQUE (med_id, fecha, hora));

CREATE TABLE IF NOT EXISTS citas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telefono TEXT NOT NULL, motivo TEXT NOT NULL, fecha_hora TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'activa',      -- activa | cancelada | pasada
    creado TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS citas_recordatorios (
    cita_id INTEGER NOT NULL REFERENCES citas(id) ON DELETE CASCADE,
    minutos INTEGER NOT NULL, PRIMARY KEY (cita_id, minutos));

CREATE TABLE IF NOT EXISTS notificaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telefono TEXT NOT NULL, mensaje TEXT NOT NULL, creado TEXT NOT NULL,
    entregado INTEGER NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS mensajes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telefono TEXT NOT NULL, rol TEXT NOT NULL, texto TEXT NOT NULL, creado TEXT NOT NULL);
"""


@contextmanager
def conexion():
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    con = sqlite3.connect(config.DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db():
    with conexion() as con:
        con.executescript(SCHEMA)


# ------------------------------------------------------------------ usuarios / sesión
def get_usuario(telefono):
    with conexion() as con:
        fila = con.execute("SELECT * FROM usuarios WHERE telefono=?", (telefono,)).fetchone()
    return dict(fila) if fila else None


def crear_usuario(telefono, nombre=None):
    with conexion() as con:
        con.execute("INSERT OR IGNORE INTO usuarios VALUES (?,?,?)", (telefono, nombre, ts()))


def actualizar_nombre(telefono, nombre):
    with conexion() as con:
        con.execute("UPDATE usuarios SET nombre=? WHERE telefono=?", (nombre, telefono))


def get_sesion(telefono):
    with conexion() as con:
        fila = con.execute("SELECT * FROM sesiones WHERE telefono=?", (telefono,)).fetchone()
    if not fila or not fila["estado"]:
        return None, {}
    if a_dt(fila["actualizado"]) < ahora() - timedelta(minutes=config.SESION_EXPIRA_MIN):
        limpiar_sesion(telefono)
        return None, {}
    return fila["estado"], json.loads(fila["datos"] or "{}")


def set_sesion(telefono, estado, datos=None):
    with conexion() as con:
        con.execute(
            "INSERT INTO sesiones VALUES (?,?,?,?) ON CONFLICT(telefono) DO UPDATE SET "
            "estado=excluded.estado, datos=excluded.datos, actualizado=excluded.actualizado",
            (telefono, estado, json.dumps(datos or {}), ts()))


def limpiar_sesion(telefono):
    with conexion() as con:
        con.execute("DELETE FROM sesiones WHERE telefono=?", (telefono,))


# ------------------------------------------------------------------ medicamentos
def _med(fila):
    d = dict(fila)
    d["horas"] = d["horas"].split(",")
    return d


def agregar_medicamento(telefono, nombre, dosis, horas, fecha_inicio, fecha_fin):
    with conexion() as con:
        # si ya existía uno activo con el mismo nombre, se reemplaza
        con.execute("UPDATE medicamentos SET activo=0 WHERE telefono=? AND activo=1 "
                    "AND lower(nombre)=lower(?)", (telefono, nombre))
        cur = con.execute(
            "INSERT INTO medicamentos (telefono,nombre,dosis,horas,fecha_inicio,fecha_fin,creado) "
            "VALUES (?,?,?,?,?,?,?)",
            (telefono, nombre, dosis, ",".join(horas), fecha_inicio, fecha_fin, ts()))
        return cur.lastrowid


def listar_medicamentos(telefono):
    with conexion() as con:
        filas = con.execute("SELECT * FROM medicamentos WHERE telefono=? AND activo=1 "
                            "ORDER BY nombre", (telefono,)).fetchall()
    return [_med(f) for f in filas]


def medicamentos_activos():
    with conexion() as con:
        filas = con.execute("SELECT * FROM medicamentos WHERE activo=1").fetchall()
    return [_med(f) for f in filas]


def desactivar_medicamento(med_id):
    with conexion() as con:
        con.execute("UPDATE medicamentos SET activo=0 WHERE id=?", (med_id,))
        con.execute("UPDATE tomas SET estado='cancelada' WHERE med_id=? "
                    "AND estado IN ('enviado','pospuesta')", (med_id,))


# ------------------------------------------------------------------ tomas
def registrar_toma(med_id, fecha, hora, estado, enviado_en=None):
    """Devuelve True si se creó (False si ya existía → evita avisar dos veces)."""
    with conexion() as con:
        cur = con.execute("INSERT OR IGNORE INTO tomas (med_id,fecha,hora,estado,enviado_en) "
                          "VALUES (?,?,?,?,?)",
                          (med_id, fecha, hora, estado, ts(enviado_en) if enviado_en else None))
        return cur.rowcount == 1


def actualizar_toma(toma_id, estado, recordar_en=None, enviado_en=None):
    with conexion() as con:
        con.execute("UPDATE tomas SET estado=?, recordar_en=?, "
                    "enviado_en=COALESCE(?, enviado_en) WHERE id=?",
                    (estado, ts(recordar_en) if recordar_en else None,
                     ts(enviado_en) if enviado_en else None, toma_id))


_SELECT_TOMA = ("SELECT t.*, m.nombre, m.dosis, m.telefono FROM tomas t "
                "JOIN medicamentos m ON m.id = t.med_id ")


def tomas_pendientes(telefono):
    with conexion() as con:
        filas = con.execute(
            _SELECT_TOMA + "WHERE m.telefono=? AND t.estado IN ('enviado','pospuesta') "
            "ORDER BY t.enviado_en DESC, t.id DESC", (telefono,)).fetchall()
    return [dict(f) for f in filas]


def tomas_pospuestas_vencidas(ahora_):
    with conexion() as con:
        filas = con.execute(_SELECT_TOMA + "WHERE t.estado='pospuesta' AND t.recordar_en <= ?",
                            (ts(ahora_),)).fetchall()
    return [dict(f) for f in filas]


def tomas_sin_respuesta(limite):
    with conexion() as con:
        filas = con.execute(_SELECT_TOMA + "WHERE t.estado='enviado' AND t.enviado_en <= ?",
                            (ts(limite),)).fetchall()
    return [dict(f) for f in filas]


def tomas_usuario(telefono):
    with conexion() as con:
        filas = con.execute(_SELECT_TOMA + "WHERE m.telefono=? ORDER BY t.fecha, t.hora",
                            (telefono,)).fetchall()
    return [dict(f) for f in filas]


def tomas_del_dia(telefono, fecha):
    with conexion() as con:
        filas = con.execute(_SELECT_TOMA + "WHERE m.telefono=? AND t.fecha=?",
                            (telefono, fecha)).fetchall()
    return {(f["med_id"], f["hora"]): f["estado"] for f in filas}


# ------------------------------------------------------------------ citas
def agregar_cita(telefono, motivo, fecha_hora):
    with conexion() as con:
        cur = con.execute("INSERT INTO citas (telefono,motivo,fecha_hora,creado) VALUES (?,?,?,?)",
                          (telefono, motivo, ts(fecha_hora), ts()))
        return cur.lastrowid


def listar_citas(telefono):
    with conexion() as con:
        filas = con.execute("SELECT * FROM citas WHERE telefono=? AND estado='activa' "
                            "ORDER BY fecha_hora", (telefono,)).fetchall()
    return [dict(f) for f in filas]


def citas_activas():
    with conexion() as con:
        filas = con.execute("SELECT * FROM citas WHERE estado='activa'").fetchall()
    return [dict(f) for f in filas]


def cita_en(telefono, fecha_hora):
    with conexion() as con:
        fila = con.execute("SELECT * FROM citas WHERE telefono=? AND estado='activa' "
                           "AND fecha_hora=?", (telefono, ts(fecha_hora))).fetchone()
    return dict(fila) if fila else None


def cambiar_estado_cita(cita_id, estado):
    with conexion() as con:
        con.execute("UPDATE citas SET estado=? WHERE id=?", (estado, cita_id))


def recordatorio_cita_enviado(cita_id, minutos):
    with conexion() as con:
        return con.execute("SELECT 1 FROM citas_recordatorios WHERE cita_id=? AND minutos=?",
                           (cita_id, minutos)).fetchone() is not None


def marcar_recordatorio_cita(cita_id, minutos):
    with conexion() as con:
        con.execute("INSERT OR IGNORE INTO citas_recordatorios VALUES (?,?)", (cita_id, minutos))


# ------------------------------------------------------------------ notificaciones y chat
def crear_notificacion(telefono, mensaje, entregado=0):
    with conexion() as con:
        con.execute("INSERT INTO notificaciones (telefono,mensaje,creado,entregado) VALUES (?,?,?,?)",
                    (telefono, mensaje, ts(), entregado))


def tomar_notificaciones(telefono):
    """Devuelve las notificaciones pendientes y las marca como entregadas."""
    with conexion() as con:
        filas = con.execute("SELECT * FROM notificaciones WHERE telefono=? AND entregado=0 "
                            "ORDER BY id", (telefono,)).fetchall()
        con.executemany("UPDATE notificaciones SET entregado=1 WHERE id=?",
                        [(f["id"],) for f in filas])
    return [dict(f) for f in filas]


def guardar_mensaje(telefono, rol, texto):
    with conexion() as con:
        con.execute("INSERT INTO mensajes (telefono,rol,texto,creado) VALUES (?,?,?,?)",
                    (telefono, rol, texto, ts()))


def historial(telefono, limite=200):
    with conexion() as con:
        filas = con.execute("SELECT rol,texto,creado FROM mensajes WHERE telefono=? "
                            "ORDER BY id DESC LIMIT ?", (telefono, limite)).fetchall()
    return [dict(f) for f in reversed(filas)]


def borrar_datos(telefono):
    with conexion() as con:
        for tabla in ("mensajes", "notificaciones", "sesiones", "citas", "medicamentos", "usuarios"):
            con.execute(f"DELETE FROM {tabla} WHERE telefono=?", (telefono,))
