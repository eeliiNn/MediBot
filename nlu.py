import difflib
import re
import unicodedata
from datetime import date, timedelta


def norm(texto):
    """Minúsculas y sin tildes, SIN cambiar la longitud del texto."""
    return "".join(unicodedata.normalize("NFD", c)[0] for c in texto).lower()


class Texto:
    """Texto original + versión normalizada. Cada entidad encontrada se 'consume' (se borra),
    y lo que sobra al final suele ser el nombre del medicamento o el motivo de la cita."""

    def __init__(self, original):
        self.orig = original
        self.n = norm(original)

    def consumir(self, span):
        a, b = span
        self.orig = self.orig[:a] + " " * (b - a) + self.orig[b:]
        self.n = self.n[:a] + " " * (b - a) + self.n[b:]

    @property
    def resto(self):
        return re.sub(r"\s+", " ", self.orig).strip()


# ===================================================================== ENTIDADES
MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
         "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
DIAS_SEM = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
NUM_PAL = {"un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
           "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "doce": 12, "quince": 15, "veinte": 20,
           "treinta": 30}
_NUM = r"(\d{1,3}|uno|una|un|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|doce|quince|veinte|treinta)"


def _num(s):
    return int(s) if s.isdigit() else NUM_PAL[s]


# ---------------------------------------------------------------- frecuencia
_F_INTERVALO = re.compile(r"\bcada\s+" + _NUM + r"\s*(?:horas?|hrs?|h)\b")
_F_VECES = re.compile(r"\b" + _NUM + r"\s+(?:vez|veces)\s+(?:(?:al|por|en\s+el|x)\s*dia|diarias?|diarios?)\b")
_F_DIARIA = re.compile(r"\b(?:todos\s+los\s+dias|cada\s+dia|diari[oa]s?|diariamente)\b")


def extraer_frecuencia(t):
    """-> {'intervalo': 8} | {'veces': 3} | {}"""
    m = _F_INTERVALO.search(t.n)
    if m and 1 <= _num(m.group(1)) <= 24:
        t.consumir(m.span())
        return {"intervalo": _num(m.group(1))}
    m = _F_VECES.search(t.n)
    if m:
        t.consumir(m.span())
        return {"veces": _num(m.group(1))}
    m = _F_DIARIA.search(t.n)
    if m:
        t.consumir(m.span())
        return {"veces": 1}
    return {}


# ---------------------------------------------------------------- duración
_DUR = re.compile(r"\b(?:por|durante|x)?\s*" + _NUM + r"\s*(dias?|semanas?|mes|meses)\b")
_INDEF = re.compile(r"\b(?:siempre|indefinid[oa]|permanente|cronic[oa]|de\s+por\s+vida|sin\s+fin|continu[oa])\b")


def extraer_duracion(t):
    """-> días (int) | 0 si es tratamiento continuo | None si no se mencionó"""
    m = _DUR.search(t.n)
    if m:
        unidad = m.group(2)
        factor = 7 if unidad.startswith("semana") else 30 if unidad.startswith("mes") else 1
        t.consumir(m.span())
        return _num(m.group(1)) * factor
    m = _INDEF.search(t.n)
    if m:
        t.consumir(m.span())
        return 0
    return None


# ---------------------------------------------------------------- dosis
_UNIDADES = (r"(mg|mcg|gr|g|ml|gotas?|tabletas?|tabs?|pastillas?|capsulas?|comprimidos?|cucharadas?|"
             r"cucharaditas?|ampollas?|unidades?|ui|sobres?|puffs?|inyecciones?|parches?|pildoras?)")
_DOSIS = re.compile(r"\b(\d+(?:[.,]\d+)?|media|medio|un|una|uno|dos|tres|cuatro)\s*" + _UNIDADES + r"\b")
_ACENTOS = {"capsula": "cápsula", "capsulas": "cápsulas", "pildora": "píldora", "pildoras": "píldoras"}


def extraer_dosis(t):
    """-> '500 mg' | '1 tableta' | '1/2 pastilla' | None"""
    m = _DOSIS.search(t.n)
    if not m:
        return None
    cantidad, unidad = m.group(1), m.group(2)
    if cantidad in ("media", "medio"):
        cantidad = "1/2"
    elif cantidad in NUM_PAL:
        cantidad = str(NUM_PAL[cantidad])
    unidad = _ACENTOS.get(unidad, unidad)
    t.consumir(m.span())
    return f"{cantidad.replace(',', '.')} {unidad}"


# ---------------------------------------------------------------- horas
_HORA = re.compile(
    r"(?P<pref>\ba\s+las?\s+|\bla\s+)?\b(?P<h>\d{1,2})(?:[:h](?P<m>\d{2}))?"
    r"(?:\s*(?P<ampm>[ap]\s?\.?\s?m\b\.?))?"
    r"(?:\s+(?:de\s+la\s+|en\s+la\s+|de\s+)(?P<per>manana|tarde|noche|madrugada)\b)?")
_MEDIO = re.compile(r"\b(mediodia|medianoche)\b")


def _a_hhmm(h, m, ampm, per):
    if m > 59:
        return None
    ampm = re.sub(r"[\s.]", "", ampm) if ampm else None
    if ampm:
        if not 1 <= h <= 12:
            return None
        h = (h % 12) + (12 if ampm == "pm" else 0)
    elif per:
        if h > 12:
            return None
        if per == "tarde":
            h = h + 12 if h < 12 else h
        elif per == "noche":
            h = 0 if h == 12 else (h + 12 if h >= 6 else h)
        else:                       # mañana / madrugada
            h = 0 if h == 12 else h
    if h > 23:
        return None
    return f"{h:02d}:{m:02d}"


def extraer_horas(t, solo_numero=False):
    """-> lista ordenada de 'HH:MM'. Con solo_numero=True acepta también un '8' suelto
    (1-6 se interpreta como la tarde; 7-12 como la mañana)."""
    horas, spans = [], []
    for m in _HORA.finditer(t.n):
        if not (m.group("pref") or m.group("m") or m.group("ampm") or m.group("per")):
            continue                                   # un número cualquiera no es una hora
        valor = _a_hhmm(int(m.group("h")), int(m.group("m") or 0), m.group("ampm"), m.group("per"))
        if valor:
            horas.append(valor)
            spans.append(m.span())
    for m in _MEDIO.finditer(t.n):
        horas.append("12:00" if m.group(1) == "mediodia" else "00:00")
        spans.append(m.span())
    if not horas and solo_numero:
        m = re.fullmatch(r"\s*(\d{1,2})\s*", t.n)
        if m and int(m.group(1)) <= 23:
            h = int(m.group(1))
            horas.append(f"{h + 12 if 1 <= h <= 6 else h:02d}:00")
            spans.append(m.span())
    for sp in spans:
        t.consumir(sp)
    return sorted(set(horas))


# ---------------------------------------------------------------- fechas
def _construir_fecha(d, mes, anio, hoy):
    if anio:
        y = int(anio) + (2000 if int(anio) < 100 else 0)
        try:
            return date(y, mes, d)
        except ValueError:
            return "invalida"
    for y in (hoy.year, hoy.year + 1):
        try:
            f = date(y, mes, d)
        except ValueError:
            continue
        if f >= hoy:
            return f
    return "invalida"


def extraer_fecha(t, hoy):
    """-> date | 'invalida' | None"""
    n = t.n
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", n)
    if m:
        t.consumir(m.span())
        return _construir_fecha(int(m.group(1)), int(m.group(2)), m.group(3), hoy)
    m = re.search(r"\b(\d{1,2})\s+de\s+(" + "|".join(MESES) + r")(?:\s+(?:de|del)\s+(\d{4}))?\b", n)
    if m:
        t.consumir(m.span())
        return _construir_fecha(int(m.group(1)), MESES[m.group(2)], m.group(3), hoy)
    m = re.search(r"\bel\s+(?:dia\s+)?(\d{1,2})\b", n)
    if m:
        t.consumir(m.span())
        d = int(m.group(1))
        y, mes = hoy.year, hoy.month
        for _ in range(3):
            try:
                f = date(y, mes, d)
                if f >= hoy:
                    return f
            except ValueError:
                pass
            mes += 1
            if mes > 12:
                mes, y = 1, y + 1
        return "invalida"
    m = re.search(r"\bpasado\s+manana\b", n)
    if m:
        t.consumir(m.span())
        return hoy + timedelta(days=2)
    m = re.search(r"\bmanana\b", n)
    if m:
        t.consumir(m.span())
        return hoy + timedelta(days=1)
    m = re.search(r"\bhoy\b", n)
    if m:
        t.consumir(m.span())
        return hoy
    m = re.search(r"\ben\s+" + _NUM + r"\s+(dias?|semanas?)\b", n)
    if m:
        t.consumir(m.span())
        return hoy + timedelta(days=_num(m.group(1)) * (7 if m.group(2).startswith("semana") else 1))
    m = re.search(r"\b(?:(?:el|este|proximo|para)\s+)*(" + "|".join(DIAS_SEM) + r")\b", n)
    if m:
        t.consumir(m.span())
        delta = (DIAS_SEM[m.group(1)] - hoy.weekday()) % 7 or 7
        return hoy + timedelta(days=delta)
    return None


def extraer_minutos(texto):
    """'posponer 20 minutos' -> 20 | 'en una hora' -> 60 | None"""
    n = norm(texto)
    if re.search(r"\bmedia\s+hora\b", n):
        return 30
    m = re.search(_NUM + r"\s*(min|minutos?|horas?|hrs?|h)\b", n)
    if not m:
        return None
    v = _num(m.group(1))
    return min(v * 60 if m.group(2).startswith(("h", "hr")) else v, 360)


# ---------------------------------------------------------------- nombres / motivos
_STOP_COMUN = set("""quiero quisiera necesito deseo puedes podrias podria por favor porfa pls plis registrar registra
registrame registro agregar agrega agregame anadir anade anademe apuntar apunta programar programa pon poner ponme
crear crea recuerdame recordarme recordar recordatorio recordatorios tomar tomo tomando tengo tener debo hay un una
uno unos unas el la los las lo le me mi mis tu de del al a en por para con y o e que es se nuevo nueva nuevos nuevas
hola buenas buenos dias dia tardes noches hoy manana tambien ademas si no gracias ok dosis veces vez hora horas cada
durante ya""".split())
STOP_MED = _STOP_COMUN | set("""medicamento medicamentos medicina medicinas pastilla pastillas tratamiento pildora
pildoras tableta tabletas jarabe llamado llama nombre cita citas""".split())
STOP_CITA = _STOP_COMUN | set("""agendar agenda cita citas consulta consultas sacar hacer reservar turno medica
medicas cuando tipo tiene fecha""".split())
STOP_PERSONA = set("""hola buenas buenos dias tardes noches me llamo mi nombre es soy yo llamame puedes llamarme hey
el la un una llamado por favor""".split())


def limpiar_nombre(texto, stop, max_palabras=6):
    """Quita palabras vacías al inicio y al final y devuelve el resto con formato de título."""
    palabras = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9\-]+", texto)
    largas = [s for s in stop if len(s) >= 6]

    def vacia(p):
        w = norm(p)
        return w in stop or (len(w) >= 6 and bool(difflib.get_close_matches(w, largas, n=1, cutoff=0.85)))

    while palabras and vacia(palabras[0]):
        palabras.pop(0)
    while palabras and vacia(palabras[-1]):
        palabras.pop()
    nombre = " ".join(palabras[:max_palabras])
    if not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", nombre) or len(nombre) < 2:
        return ""
    return nombre.title()


# ===================================================================== INTENCIONES
# El orden del diccionario es la prioridad en caso de empate.
_KW = {
    "tomada": [("ya me lo tome", 3), ("ya me la tome", 3), ("me lo tome", 3), ("me la tome", 3),
               ("ya lo tome", 3), ("ya la tome", 3), ("ya tome", 3), ("tome", 2), ("tomada", 1),
               ("tomado", 1), ("listo", 1), ("hecho", 1), ("confirmo", 1)],
    "posponer": [("posponer", 3), ("pospon", 3), ("pospone", 3), ("posponla", 3), ("mas tarde", 2),
                 ("despues", 1), ("luego", 1), ("en un rato", 2), ("snooze", 3), ("ahorita no", 3),
                 ("recuerdame en", 3)],
    "omitida": [("no la tome", 3), ("no lo tome", 3), ("no tome", 3), ("me la salte", 3),
                ("me lo salte", 3), ("se me paso", 3), ("olvide tomar", 3), ("omitir", 1),
                ("omito", 1), ("omitida", 1), ("salte", 1)],
    "ver_medicamentos": [(p, 3) for p in (
        "mis medicamentos", "mis medicinas", "mis pastillas", "mis tratamientos", "ver medicamentos",
        "ver medicinas", "lista de medicamentos", "mostrar medicamentos", "que medicamentos",
        "que medicinas", "medicamentos activos", "tratamientos activos")],
    "ver_citas": [(p, 3) for p in (
        "mis citas", "ver citas", "proximas citas", "lista de citas", "que citas", "mostrar citas",
        "citas pendientes", "citas programadas", "mi proxima cita")],
    "eliminar": [("eliminar", 2), ("borrar", 2), ("quitar", 2), ("cancelar", 2), ("anular", 2),
                 ("dejar de tomar", 3), ("ya no tomo", 3), ("ya no necesito", 3), ("eliminar cita", 3),
                 ("cancelar cita", 3), ("borrar cita", 3), ("eliminar medicamento", 3)],
    "registrar_medicamento": [
        ("registrar medicamento", 3), ("registrar medicina", 3), ("agregar medicamento", 3),
        ("anadir medicamento", 3), ("nuevo medicamento", 3), ("recordar medicamento", 3),
        ("recordatorio de medicamento", 3), ("agregar medicina", 3), ("nueva medicina", 3),
        ("tengo que tomar", 2), ("debo tomar", 2), ("medicamento", 1), ("medicamentos", 1),
        ("medicina", 1), ("medicinas", 1), ("pastilla", 1), ("pastillas", 1), ("pildora", 1),
        ("pildoras", 1), ("tableta", 1), ("tabletas", 1), ("jarabe", 1), ("antibiotico", 1),
        ("tratamiento", 1), ("dosis", 1), ("tomo", 1), ("tomar", 1)],
    "registrar_cita": [
        ("agendar cita", 3), ("nueva cita", 3), ("programar cita", 3), ("sacar cita", 3),
        ("reservar cita", 3), ("tengo cita", 2), ("agendar", 2), ("cita", 1), ("citas", 1),
        ("consulta", 1), ("turno", 1), ("reservar", 1), ("doctor", 1), ("doctora", 1), ("medico", 1),
        ("especialista", 1), ("chequeo", 1), ("dentista", 1), ("cardiologo", 1), ("pediatra", 1),
        ("ginecologo", 1), ("oculista", 1), ("oftalmologo", 1), ("dermatologo", 1),
        ("laboratorio", 1), ("examen", 1)],
    "horarios": [("horario", 2), ("horarios", 2), ("mi agenda", 3), ("agenda de hoy", 3), ("agenda", 1),
                 ("que me toca", 3), ("que tengo hoy", 3), ("proxima toma", 3), ("proxima dosis", 3),
                 ("mi dia", 2), ("pendientes", 1), ("que sigue", 2), ("para hoy", 1)],
    "adherencia": [("reporte", 2), ("estadisticas", 2), ("estadistica", 2), ("adherencia", 3),
                   ("como voy", 3), ("progreso", 2), ("mi progreso", 3), ("historial", 2), ("resumen", 1),
                   ("racha", 2), ("cumplimiento", 2)],
    "nombre": [("me llamo", 3), ("mi nombre es", 3), ("cambiar mi nombre", 3), ("cambiar nombre", 3),
               ("llamame", 3)],
    "servicios": [("servicios", 2), ("servicio", 2), ("ayuda", 2), ("ayudame", 2), ("help", 2),
                  ("que haces", 3), ("que puedes hacer", 3), ("que ofreces", 3), ("funciones", 2),
                  ("como funciona", 3), ("como te uso", 3), ("no entiendo", 2), ("comandos", 2),
                  ("para que sirves", 3), ("como se usa", 3)],
    "menu": [("menu", 3), ("inicio", 2), ("opciones", 2), ("volver al menu", 3), ("empezar", 1),
             ("comenzar", 1), ("start", 1)],
    "despedida": [("gracias", 2), ("adios", 3), ("chao", 3), ("chau", 3), ("bye", 3), ("hasta luego", 3),
                  ("nada mas", 2), ("salir", 2), ("eso es todo", 3), ("no gracias", 3), ("hasta pronto", 3)],
    "saludo": [("hola", 2), ("holi", 2), ("buenas", 2), ("buenos dias", 2), ("buenas tardes", 2),
               ("buenas noches", 2), ("hey", 1), ("saludos", 2), ("que tal", 1), ("buen dia", 2)],
}

_COMPILADAS = {i: [(re.compile(r"\b" + re.escape(f) + r"\b"), p) for f, p in kws] for i, kws in _KW.items()}

# vocabulario para corregir errores de escritura ("medicamneto" -> "medicamento")
_VOCAB = {}
for _i, _kws in _KW.items():
    for _f, _p in _kws:
        if " " not in _f and len(_f) >= 6:
            _VOCAB.setdefault(_f, []).append((_i, _p))
_VOCAB_LISTA = list(_VOCAB)
_PRIORIDAD = {i: k for k, i in enumerate(_KW)}


def detectar_intencion(texto):
    """-> (intención, puntaje) o (None, 0)"""
    n = norm(texto)
    puntajes = {}
    for intencion, reglas in _COMPILADAS.items():
        s = sum(p for rx, p in reglas if rx.search(n))
        if s:
            puntajes[intencion] = s

    for palabra in re.findall(r"[a-z]+", n):          # tolerancia a errores de escritura
        if len(palabra) < 6 or palabra in _VOCAB:
            continue
        cerca = difflib.get_close_matches(palabra, _VOCAB_LISTA, n=1, cutoff=0.84)
        if cerca:
            for intencion, p in _VOCAB[cerca[0]]:
                puntajes[intencion] = puntajes.get(intencion, 0) + p

    # pistas por entidades: "paracetamol 500 mg cada 8 horas" es un medicamento aunque no diga la palabra
    t = Texto(texto)
    if extraer_dosis(t) or extraer_frecuencia(t):
        puntajes["registrar_medicamento"] = puntajes.get("registrar_medicamento", 0) + 3

    if not puntajes:
        return None, 0
    mejor = max(puntajes.items(), key=lambda kv: (kv[1], -_PRIORIDAD[kv[0]]))
    return mejor


# ---------------------------------------------------------------- sí / no
_SI = {"si", "sip", "sii", "claro", "ok", "okay", "dale", "correcto", "confirmo", "confirmar", "confirma",
       "exacto", "afirmativo", "yes", "vale", "listo", "seguro", "perfecto", "adelante", "aja"}
_NO = {"no", "nop", "nel", "negativo", "nunca", "nope", "cancelar", "cancela"}


def _tokens(n):
    return re.findall(r"[a-z0-9]+", n)


def es_si(n):
    tk = _tokens(n)
    return bool(tk) and tk[0] in _SI and "no" not in tk


def es_no(n):
    tk = _tokens(n)
    return bool(tk) and tk[0] in _NO
