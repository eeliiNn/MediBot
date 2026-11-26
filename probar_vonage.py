"""probar_vonage.py - Comprueba que tu computadora puede enviar WhatsApp por Vonage.

Uso:  python probar_vonage.py 50371110776 "Hola desde MediBot"
(el número va con código de país, sin + ni espacios, y debe estar unido al sandbox)
"""
import os
import sys

os.environ["MODO"] = "vonage"
import config
import mensajeria

if len(sys.argv) < 2:
    sys.exit(__doc__)
if not config.vonage_listo():
    sys.exit("Faltan VONAGE_API_KEY y VONAGE_API_SECRET en el archivo .env")

texto = sys.argv[2] if len(sys.argv) > 2 else "Hola, soy MediBot 🩺 (mensaje de prueba)"
print(f"Enviando a {sys.argv[1]} desde {config.VONAGE_WHATSAPP_NUMBER} usando {config.vonage_url()} ...")
print("✅ Enviado, revisa tu WhatsApp" if mensajeria.enviar_texto(sys.argv[1], texto)
      else "❌ No se pudo enviar (el motivo apareció arriba, en la línea [vonage])")
