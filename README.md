# 🩺 MediBot — Chatbot de medicamentos y citas médicas

Chatbot en **Python + Flask** que permite registrar **medicamentos** y **citas médicas** y envía
**recordatorios automáticos** en los horarios establecidos. Funciona en **modo local** (simulador de
WhatsApp en el navegador) y en **WhatsApp real** mediante Twilio Sandbox, sin cambiar el código del bot.

## ▶️ Cómo ejecutarlo

```bash
python -m venv venv
venv\Scripts\activate            # Windows   (Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt
python app.py
```

Abre **http://localhost:5000** → verás un chat estilo WhatsApp.

Otras formas de probarlo:

| Comando | Para qué sirve |
|---|---|
| `python consola.py` | Chatear desde la terminal |
| `python test_chatbot.py` | Pruebas automáticas del bot (no tocan tus datos) |
| `python test_vonage.py` | Prueba del canal de Vonage, sin internet |
| `python probar_vonage.py <número>` | Envía un WhatsApp de prueba por Vonage |

## 💬 Qué puede hacer

| Función | Ejemplo de lo que escribe el usuario |
|---|---|
| Registrar medicamento (paso a paso) | `1` o `registrar medicamento` |
| Registrar medicamento (una sola frase) | `Tomo paracetamol 500 mg cada 8 horas a las 8am por 5 días` |
| Agendar cita | `Tengo cita con el dentista el viernes a las 3pm` |
| Ver medicamentos / citas | `mis medicamentos`, `mis citas` |
| Agenda del día | `mi agenda` |
| Confirmar una toma | `tomé`, `ya me la tomé` |
| Posponer un recordatorio | `posponer`, `posponer 20 minutos` |
| Omitir una dosis | `omitir`, `no la tomé` |
| Ver progreso y racha | `mi progreso` |
| Eliminar medicamento o cita | `eliminar paracetamol`, `cancelar cita` |
| Volver al inicio / salir de un flujo | `menu`, `cancelar` |

## 🧠 Diseño conversacional (como la guía)

```
Mensaje ─► DETECCIÓN DE LA INTENCIÓN ─► DETECCIÓN DE LA ENTIDAD ─► RESPUESTA / CONFIRMACIÓN
            (nlu.py · detectar_intencion)   (nlu.py · extraer_*)       (chatbot.py)
```

**Intenciones:** saludo, menú, servicios/ayuda, horarios (agenda), registrar medicamento, registrar cita,
ver medicamentos, ver citas, tomada, posponer, omitida, eliminar, progreso, cambiar nombre, despedida.

**Entidades:** hora (`8am`, `3:30 pm`, `7 de la noche`), fecha (`mañana`, `el viernes`, `24 de octubre`, `24/10`),
dosis (`500 mg`, `1 tableta`), frecuencia (`cada 8 horas`, `3 veces al día`), duración (`5 días`, `2 semanas`, `siempre`),
nombre del medicamento y motivo de la cita.

## ✨ Mejoras e innovaciones sobre la funcionalidad mínima

1. **Lenguaje natural + llenado de datos faltantes:** si el usuario da todos los datos en una frase, el bot no vuelve a preguntarlos; si falta algo, solo pregunta lo que falta.
2. **Tolerancia a errores de escritura** (`medicamneto` → `medicamento`) y a tildes/mayúsculas.
3. **Frecuencia inteligente:** "cada 8 horas" o "3 veces al día" se convierten solos en horarios concretos.
4. **Confirmar / posponer / omitir** cada dosis, con tiempo personalizado (`posponer 20 minutos`).
5. **Recordatorios de cita dobles:** 1 día antes y 1 hora antes (configurable en `config.py`).
6. **Reporte de adherencia:** porcentaje total, últimos 7 días, por medicamento y **racha** de días.
7. **Agenda diaria** con estado de cada dosis (✅ tomada, ⏳ pendiente, ❌ omitida).
8. **Validaciones:** no permite citas en el pasado ni dos citas a la misma hora; avisa al terminar un tratamiento.
9. **Varios usuarios** (cada número tiene sus propios datos) y datos guardados en **SQLite**.
10. **Modo demostración:** panel para adelantar el reloj y ver los recordatorios al instante.
11. **Triple modo:** simulador local, WhatsApp con Vonage o Twilio, con el mismo cerebro.

## 🗂️ Estructura del proyecto

```
app.py            Servidor Flask: simulador web, API y webhooks (Vonage y Twilio)
mensajeria.py     Envío de mensajes por Vonage, Twilio o simulador
chatbot.py        Flujos conversacionales (registrar, consultar, confirmar, eliminar, progreso)
nlu.py            Intenciones y entidades (reglas + tolerancia a errores)
recordatorios.py  Motor de recordatorios automáticos (hilo en segundo plano)
database.py       Todas las consultas SQLite
config.py         Configuración (.env, tiempos de recordatorio)
formato.py        Fechas, horas y barras de progreso en español
reloj.py          Reloj con desfase para la demostración
consola.py        Chat por terminal
test_chatbot.py   Pruebas automáticas
templates/index.html   Simulador de WhatsApp
```

## 🎬 Guion sugerido para la defensa (3–4 minutos)

1. Abrir el simulador y escribir `hola` → se presenta el bot y pregunta el nombre.
2. Registrar un medicamento en una sola frase: `Tomo ibuprofeno 400 mg 3 veces al día por 5 días` → mostrar la confirmación y los horarios generados.
3. Agendar una cita: `tengo cita con el dentista mañana a las 3pm`.
4. En el panel de demostración pulsar **+1 hora** hasta que llegue el recordatorio de la dosis.
5. Responder `posponer 10 minutos`, adelantar el reloj y mostrar el segundo aviso; luego `tomé`.
6. Pulsar **+1 día** para mostrar el aviso de cita "1 día antes" y escribir `mi progreso`.
7. Mostrar el código: `nlu.py` (intenciones/entidades) y `recordatorios.py` (cómo decide cuándo avisar).

## 📲 Conectar con WhatsApp real

El bot tiene 3 modos (`MODO` en el archivo `.env`): `local` (simulador), `vonage` y `twilio`.

### Opción A · Vonage (Messages API Sandbox)

1. **Cuenta:** crea una cuenta gratis en https://dashboard.nexmo.com (el sandbox es gratuito).
2. **Credenciales:** en la página principal del dashboard copia tu **API key** y tu **API secret**.
3. **Unirte al sandbox:** menú **Messages API Sandbox** → junto a WhatsApp pulsa **Add to sandbox** y sigue las instrucciones: envías, desde tu WhatsApp, el mensaje con la frase única que te muestra al número del sandbox. Eso agrega tu número a la lista permitida.
4. **Archivo `.env`:**
   ```
   MODO=vonage
   VONAGE_API_KEY=<tu api key>
   VONAGE_API_SECRET=<tu api secret>
   VONAGE_WHATSAPP_NUMBER=<el número "from" que aparece en el sandbox>
   VONAGE_SANDBOX=true
   ```
5. **Probar el envío** (sin servidor todavía):
   ```
   python probar_vonage.py 50371110776 "Hola desde MediBot"
   ```
   (tu número con código de país, sin `+`). Si llega a tu WhatsApp, el envío funciona.
6. **Servidor y túnel** (dos terminales):
   ```
   python app.py
   .\cloudflared.exe tunnel --url http://localhost:5000
   ```
   Copia la URL `https://algo.trycloudflare.com`.
7. **Webhooks:** en la misma página *Messages API Sandbox* → **Configure webhooks**:
   - **Inbound:** `https://algo.trycloudflare.com/vonage/inbound`
   - **Status:** `https://algo.trycloudflare.com/vonage/status`
   - Pulsa **Save webhooks**.
8. **Probar:** escríbele `hola` al número del sandbox desde tu WhatsApp.

> La URL de cloudflared **cambia cada vez** que lo reinicias: pega la nueva en los dos webhooks.
> Límites del sandbox: **100 mensajes al mes** y 1 por segundo. Ahorra mensajes: haz tus pruebas con el simulador
> local y usa WhatsApp real solo para ensayar y para la defensa.
> Los recordatorios solo llegan si escribiste al bot en las últimas 24 horas (regla de WhatsApp).
> Una cuenta de Vonage nueva puede pedir verificación; hazla con tiempo.

**Si algo falla, mira la terminal de `python app.py`:**

| Síntoma | Causa probable |
|---|---|
| No aparece `POST /vonage/inbound` en la terminal | Webhook sin guardar, URL del túnel vieja, o túnel apagado |
| `[vonage] Error 401` | API key o secret mal copiados en `.env` |
| `[vonage] Error 422` | Tu número no está unido al sandbox, o pasaron más de 24 h sin escribirle al bot |
| `[vonage] Error 429` | Se acabaron los 100 mensajes del mes |
| `MODO=local: llegó un mensaje...` | Olvidaste poner `MODO=vonage` en `.env` |

**Tip para mostrar un recordatorio real en vivo:** registra un medicamento con una hora 2–3 minutos en el futuro
(por ejemplo `Registrar ibuprofeno 400 mg a las 3:47 pm`, con la hora real de tu computadora) y espera.

Para probar el canal de Vonage sin internet: `python test_vonage.py`.

### Opción B · Twilio Sandbox

1. En `.env` pon `MODO=twilio` y copia `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` y `TWILIO_PHONE_NUMBER`.
2. `python app.py` y, en otra terminal, `.\cloudflared.exe tunnel --url http://localhost:5000`.
3. En Twilio → *Try WhatsApp → Sandbox settings*, pega la URL en **When a message comes in** (POST). Funciona con `/` o `/whatsapp`.
4. Escribe `join <tu-código>` al número del sandbox.

> 🔒 Nunca subas tu `.env` ni pegues claves en documentos o capturas: son como contraseñas.

## ⚠️ Nota
MediBot es un proyecto académico de recordatorios; no sustituye la indicación de un médico ni da consejos médicos.
