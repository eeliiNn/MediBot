import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- Twilio
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# ---------------------------------------------------------------- Vonage (Messages API)
VONAGE_API_KEY = os.getenv("VONAGE_API_KEY")
VONAGE_API_SECRET = os.getenv("VONAGE_API_SECRET")
VONAGE_WHATSAPP_NUMBER = (os.getenv("VONAGE_WHATSAPP_NUMBER") or "14157386102").strip()   # número del sandbox
VONAGE_SANDBOX = os.getenv("VONAGE_SANDBOX", "true").strip().lower() in ("1", "true", "si", "yes")
# Opcional (autenticación por JWT en lugar de API key/secret):
VONAGE_APPLICATION_ID = os.getenv("VONAGE_APPLICATION_ID")
VONAGE_PRIVATE_KEY_PATH = os.getenv("VONAGE_PRIVATE_KEY_PATH")

# "local"  -> simulador web de WhatsApp (no necesita nada externo)
# "vonage" -> WhatsApp real con Vonage (Messages API / Sandbox)
# "twilio" -> WhatsApp real mediante Twilio Sandbox
MODO = os.getenv("MODO", "local").strip().lower()

# ---------------------------------------------------------------- General
NOMBRE_BOT = "MediBot"
DB_PATH = os.getenv("DB_PATH", os.path.join(BASE_DIR, "database", "medibot.db"))
PUERTO = int(os.getenv("PORT", 5000))

# ---------------------------------------------------------------- Recordatorios
INTERVALO_SCHEDULER_SEG = 20      # cada cuántos segundos revisa si toca avisar
VENTANA_RECORDATORIO_MIN = 30     # si el bot estuvo apagado, no avisa dosis con más de 30 min de retraso
OMITIR_TRAS_MIN = 120             # dosis sin respuesta tras 2 h se marca como omitida
POSPONER_MIN = 10                 # minutos por defecto al escribir "posponer"
RECORDAR_CITA_MIN = [1440, 60]    # avisos de cita: 1 día antes y 1 hora antes
SESION_EXPIRA_MIN = 30            # si el usuario abandona una conversación, se reinicia


def a_whatsapp(numero):
    numero = (numero or "").strip()
    return numero if numero.startswith("whatsapp:") else f"whatsapp:{numero}"


def twilio_listo():
    """True solo si MODO=twilio y las credenciales parecen reales (no los textos de ejemplo)."""
    sid = TWILIO_ACCOUNT_SID or ""
    token = TWILIO_AUTH_TOKEN or ""
    return (
        MODO == "twilio"
        and sid.startswith("AC") and len(sid) == 34
        and len(token) >= 30
        and bool(TWILIO_PHONE_NUMBER)
    )


def vonage_url():
    return ("https://messages-sandbox.nexmo.com/v1/messages" if VONAGE_SANDBOX
            else "https://api.nexmo.com/v1/messages")


def vonage_listo():
    """True solo si MODO=vonage y hay credenciales (API key+secret, o Application ID + llave privada)."""
    con_clave = bool(VONAGE_API_KEY and VONAGE_API_SECRET)
    con_jwt = bool(VONAGE_APPLICATION_ID and VONAGE_PRIVATE_KEY_PATH)
    return MODO == "vonage" and (con_clave or con_jwt) and bool(VONAGE_WHATSAPP_NUMBER)
