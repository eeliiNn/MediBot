"""consola.py - Chatea con MediBot desde la terminal (sin navegador).  Uso: python consola.py"""
import threading
import time

import database as db
import recordatorios
from chatbot import procesar_mensaje

TELEFONO = "consola"


def mostrar_avisos():
    while True:
        for n in db.tomar_notificaciones(TELEFONO):
            print(f"\n🔔 {n['mensaje']}\n\nTú: ", end="", flush=True)
        time.sleep(2)


if __name__ == "__main__":
    db.init_db()
    recordatorios.iniciar_scheduler()
    threading.Thread(target=mostrar_avisos, daemon=True).start()
    print("MediBot (consola). Escribe 'salir' para terminar.\n")
    print("Bot:", procesar_mensaje(TELEFONO, "hola"), "\n")
    while True:
        try:
            texto = input("Tú: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if texto.lower() == "salir":
            break
        if texto:
            print("\nBot:", procesar_mensaje(TELEFONO, texto), "\n")
