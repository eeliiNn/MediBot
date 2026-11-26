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
