import re
from typing import List, Optional
from datetime import datetime

from google.adk.tools.tool_context import ToolContext
from vertexai import rag
from config import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_EMBEDDING_REQUESTS_PER_MIN,
)
from .utils import check_corpus_exists, get_corpus_resource_name

# ✨ Importa las funciones de base de datos (créalas según mi mensaje anterior)
try:
    from Database.db_config import save_document_metadata
    DB_AVAILABLE = True
except ImportError:
    print("⚠️ WARNING: database.db_config no disponible, metadatos no se guardarán")
    DB_AVAILABLE = False


def add_data(
    corpus_name: str,
    paths: List[str],
    tool_context: ToolContext,
    # ⬇️ Estos parámetros ahora son opcionales porque pueden venir del state
    version: Optional[str] = None,
    description: Optional[str] = None,
    uploaded_by: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> dict:
    """
    Añadir nueva data para Vertex AI RAG con metadatos.
    
    Los metadatos pueden venir de dos fuentes:
    1. Parámetros directos del tool
    2. Del state de la sesión (pending_metadata)
    """
    
    pending_metadata = tool_context.state.get('pending_metadata', {})
    
    # Prioridad: parámetros explícitos > metadata del state > defaults
    final_version = version or pending_metadata.get('version') or "1.0"
    final_description = description or pending_metadata.get('description')
    final_uploaded_by = uploaded_by or pending_metadata.get('uploaded_by') or "admin"
    final_tags = tags or pending_metadata.get('tags')
    
    print(f"📦 Metadatos a usar: version={final_version}, uploaded_by={final_uploaded_by}")
    
    if not check_corpus_exists(corpus_name, tool_context):
        return {
            "status": "error",
            "message": f"Corpus '{corpus_name}' no existe. Créalo primero usando create_corpus.",
            "corpus_name": corpus_name,
            "paths": paths,
        }

    if not paths or not all(isinstance(path, str) for path in paths):
        return {
            "status": "error",
            "message": "Paths inválidos: Proporciona una lista de URLs o rutas GCS",
            "corpus_name": corpus_name,
            "paths": paths,
        }

    # Validación de paths (tu código original)
    validated_paths = []
    invalid_paths = []
    conversions = []

    for path in paths:
        if not path or not isinstance(path, str):
            invalid_paths.append(f"{path} (Not a valid string)")
            continue

        docs_match = re.match(
            r"https:\/\/docs\.google\.com\/(?:document|spreadsheets|presentation)\/d\/([a-zA-Z0-9_-]+)(?:\/|$)",
            path,
        )
        if docs_match:
            file_id = docs_match.group(1)
            drive_url = f"https://drive.google.com/file/d/{file_id}/view"
            validated_paths.append(drive_url)
            conversions.append(f"{path} → {drive_url}")
            continue

        drive_match = re.match(
            r"https:\/\/drive\.google\.com\/(?:file\/d\/|open\?id=)([a-zA-Z0-9_-]+)(?:\/|$)",
            path,
        )
        if drive_match:
            file_id = drive_match.group(1)
            drive_url = f"https://drive.google.com/file/d/{file_id}/view"
            validated_paths.append(drive_url)
            if drive_url != path:
                conversions.append(f"{path} → {drive_url}")
            continue

        if path.startswith("gs://"):
            validated_paths.append(path)
            continue

        invalid_paths.append(f"{path} (Invalid format)")

    if not validated_paths:
        return {
            "status": "error",
            "message": "No hay paths válidos. Proporciona URLs de Google Drive o rutas GCS.",
            "corpus_name": corpus_name,
            "invalid_paths": invalid_paths,
        }

    try:
        corpus_resource_name = get_corpus_resource_name(corpus_name)

        # Configuración del chunking
        transformation_config = rag.TransformationConfig(
            chunking_config=rag.ChunkingConfig(
                chunk_size=DEFAULT_CHUNK_SIZE,
                chunk_overlap=DEFAULT_CHUNK_OVERLAP,
            ),
        )

        # Importar archivos a Vertex AI RAG
        import_result = rag.import_files(
            corpus_resource_name,
            validated_paths,
            transformation_config=transformation_config,
            max_embedding_requests_per_min=DEFAULT_EMBEDDING_REQUESTS_PER_MIN,
        )

        # Actualizar current corpus en el estado
        if not tool_context.state.get("current_corpus"):
            tool_context.state["current_corpus"] = corpus_name

        metadata_results = []
        
        if DB_AVAILABLE:
            try:
                # Listar archivos del corpus para obtener los resource names
                files = rag.list_files(corpus_name=corpus_resource_name)
                
                # Guardar metadatos para cada archivo
                for i, rag_file in enumerate(files):
                    file_display_name = getattr(rag_file, 'display_name', f"Document_{i+1}")
                    rag_file_name = rag_file.name  # Resource name completo
                    
                    # Determinar el tipo de archivo
                    file_type = None
                    original_path = validated_paths[i] if i < len(validated_paths) else ""
                    if original_path.endswith('.pdf'):
                        file_type = 'pdf'
                    elif 'spreadsheets' in original_path:
                        file_type = 'sheets'
                    elif 'document' in original_path:
                        file_type = 'docs'
                    elif 'presentation' in original_path:
                        file_type = 'slides'
                    
                    # Guardar en PostgreSQL
                    metadata_save_result = save_document_metadata(
                        rag_file_name=rag_file_name,
                        corpus_name=corpus_name,
                        display_name=file_display_name,
                        version=final_version,
                        file_path=original_path,
                        uploaded_by=final_uploaded_by,
                        description=final_description,
                        file_type=file_type,
                        tags=final_tags,
                    )
                    
                    metadata_results.append({
                        "file": file_display_name,
                        "metadata_saved": metadata_save_result.get("status") == "success"
                    })
                    
            except Exception as meta_error:
                metadata_results.append({
                    "error": f"Error guardando metadatos: {str(meta_error)}"
                })
        else:
            metadata_results.append({
                "warning": "Base de datos no configurada, metadatos no guardados"
            })

        # ✨ LIMPIAR METADATA DEL STATE DESPUÉS DE USARLA
        if 'pending_metadata' in tool_context.state:
            del tool_context.state['pending_metadata']

        conversion_msg = ""
        if conversions:
            conversion_msg = " (URLs de Google Docs convertidas a formato Drive)"

        return {
            "status": "success",
            "message": f"✅ {import_result.imported_rag_files_count} archivo(s) agregado(s) al corpus '{corpus_name}'{conversion_msg}",
            "corpus_name": corpus_name,
            "files_added": import_result.imported_rag_files_count,
            "paths": validated_paths,
            "invalid_paths": invalid_paths,
            "conversions": conversions,
            "version": final_version,
            "metadata_saved": metadata_results,
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Error agregando data al corpus: {str(e)}",
            "corpus_name": corpus_name,
            "paths": paths,
        }