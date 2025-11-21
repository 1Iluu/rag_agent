import google.adk
import pkgutil

print("=== 🕵️‍♂️ DIAGNÓSTICO ADK v0.5.0 ===")
try:
    print(f"Versión detectada: {google.adk.__version__}")
except:
    print("Versión: No tiene atributo __version__")

print("\n--- Contenido raíz de google.adk ---")
print(dir(google.adk))

print("\n--- Submódulos encontrados ---")
if hasattr(google.adk, "__path__"):
    for importer, modname, ispkg in pkgutil.iter_modules(google.adk.__path__):
        print(f"📦 {modname}")

print("\n--- Buscando 'run' o 'server' dentro de Agents ---")
try:
    from google.adk.agents import Agent
    print(f"Métodos de Agent: {[m for m in dir(Agent) if not m.startswith('_')]}")
except:
    print("No pude importar Agent para inspeccionar")