import os
import uvicorn
import json
import asyncio
import vertexai
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import Optional, Dict, Any

MY_PROJECT = "rag-netsuit"
MY_REGION = "us-central1"

print(f"🌍 FORZANDO CONEXIÓN VERTEX AI -> Proyecto: {MY_PROJECT} | Región: {MY_REGION}")
vertexai.init(project=MY_PROJECT, location=MY_REGION)

from google.adk.sessions.in_memory_session_service import InMemorySessionService
from agent import admin_agent, client_agent

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

print("🧠 Iniciando memoria en RAM...")
memory_service = InMemorySessionService()

class SimplePart:
    def __init__(self, text):
        self.text = text

class SimpleMessage:
    def __init__(self, text, role="user"):
        self.role = role
        self.parts = [SimplePart(text)]


async def run_agent_manually(
    agent, 
    prompt: str, 
    session_id: str = "default_session",
    metadata: Optional[Dict[str, Any]] = None
):
    CURRENT_USER = "default_user"
    APP_NAME = "rag_app"
    
    print(f"🤖 Procesando | Agent: {agent.name} | Session: {session_id}")

    try:
        from google.adk.runners import Runner

        # ✅ SOLUCIÓN: verificar si existe ANTES de crear
        existing_session = None
        try:
            existing_session = memory_service.get_session(
                session_id=session_id,
                user_id=CURRENT_USER,
                app_name=APP_NAME
            )
        except:
            pass  # No existe aún, es normal

        if existing_session is None:
            # Solo crear si no existe
            memory_service.create_session(
                session_id=session_id,
                user_id=CURRENT_USER,
                app_name=APP_NAME
            )
            print(f"🆕 Sesión NUEVA creada: {session_id}")
        else:
            print(f"♻️ Sesión EXISTENTE reutilizada: {session_id}")

        runner = Runner(
            agent=agent,
            app_name=APP_NAME,
            session_service=memory_service
        )

        message_object = SimpleMessage(text=prompt, role="user")

        if metadata:
            session = memory_service.get_session(session_id, CURRENT_USER, APP_NAME)
            if session and hasattr(session, 'state'):
                session.state['pending_metadata'] = metadata

        async for event in runner.run_async(
            new_message=message_object,
            session_id=session_id,
            user_id=CURRENT_USER
        ):
            content = None
            
            if hasattr(event, "text"):
                content = event.text
            elif hasattr(event, "delta"):
                content = event.delta
            elif hasattr(event, "model_response") and event.model_response:
                content = getattr(event.model_response, "text", None)
            elif hasattr(event, "content") and event.content:
                parts = getattr(event.content, "parts", [])
                if parts and hasattr(parts[0], "text"):
                    content = parts[0].text
            
            if content is None and event:
                s = str(event)
                if "Event" not in s and "Start" not in s and "End" not in s:
                    content = s

            if content:
                chunk_data = json.dumps({"text": content})
                yield f"data: {chunk_data}\n\n"

        yield "data: [DONE]\n\n"

    except Exception as e:
        print(f"❌ Error CRÍTICO en Runner: {str(e)}")
        import traceback
        traceback.print_exc()
        error_data = json.dumps({"text": f"Error Backend: {str(e)}"})
        yield f"data: {error_data}\n\n"
        yield "data: [DONE]\n\n"


@app.post("/api/streamQuery")
async def unified_stream_query(request: Request):
    """
    Endpoint unificado que recibe:
    {
      "sessionId": "abc-123",
      "message": "Lista los corpus disponibles",
      "role": "admin" | "client",
      "metadata": {  // ⬅️ OPCIONAL, solo para admin
        "version": "2.1",
        "description": "...",
        "uploaded_by": "...",
        "tags": [...]
      }
    }
    """
    body = await request.json()
    
    session_id = body.get("sessionId", str(uuid.uuid4()))
    message = body.get("message", "")
    role = body.get("role", "client")  # Default: client
    metadata = body.get("metadata", None)  # ⬅️ Opcional
    
    # Validaciones
    if not message:
        return {"error": "El mensaje no puede estar vacío"}
    
    # Seleccionar agente según el role
    if role == "admin":
        agent = admin_agent
        print(f"🔧 Usando ADMIN agent")
    else:
        agent = client_agent
        print(f"👤 Usando CLIENT agent")
    
    # Stream con metadatos opcionales
    return StreamingResponse(
        run_agent_manually(agent, message, session_id, metadata),
        media_type="text/event-stream"
    )


# ✨ ENDPOINT PARA CREAR SESIONES (Angular lo usa)
@app.post("/api/sessions")
async def create_session_endpoint():
    session_id = str(uuid.uuid4())
    return {"sessionId": session_id}


# 🔄 ENDPOINTS LEGACY (mantén compatibilidad si los usas en otro lado)
@app.post("/apps/{app_name}/users/{user_id}/sessions")
async def create_session_legacy(app_name: str, user_id: str):
    return {"session_id": str(uuid.uuid4())}

def extract_prompt(body: dict) -> str:
    new_message = body.get("new_message", {})
    prompt = new_message.get("text", "")
    
    if not prompt and "parts" in new_message:
        parts = new_message["parts"]
        if isinstance(parts, list) and len(parts) > 0:
            prompt = parts[0].get("text", "")
            
    return prompt

@app.post("/admin/run_sse")
async def admin_endpoint(request: Request):
    body = await request.json()
    prompt = extract_prompt(body)
    sid = body.get("session_id", "admin_session")
    return StreamingResponse(
        run_agent_manually(admin_agent, prompt, sid),
        media_type="text/event-stream"
    )

@app.post("/client/run_sse")
async def client_endpoint(request: Request):
    body = await request.json()
    prompt = extract_prompt(body)
    sid = body.get("session_id", "client_session")
    return StreamingResponse(
        run_agent_manually(client_agent, prompt, sid),
        media_type="text/event-stream"
    )


@app.get("/")
def health_check():
    return {"status": "ok", "version": "metadata_v1"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"\n🚀 SERVIDOR LISTO (PUERTO {port})")
    uvicorn.run(app, host="0.0.0.0", port=port)