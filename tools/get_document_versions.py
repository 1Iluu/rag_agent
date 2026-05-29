from typing import Optional
from google.adk.tools.tool_context import ToolContext
from Database.db_config import get_document_metadata


def get_document_versions(
    corpus_name: Optional[str] = None,
    version: Optional[str] = None,
    tool_context: ToolContext = None,
) -> dict:
    """
    Obtiene el historial de versiones de documentos guardados en el corpus.
    
    Args:
        corpus_name: Filtrar por nombre de corpus (opcional)
        version: Filtrar por versión específica (opcional)
        
    Returns:
        Lista de documentos con sus metadatos de versión
    """
    try:
        documents = get_document_metadata(corpus_name=corpus_name, version=version)
        
        if isinstance(documents, dict) and "error" in documents:
            return {
                "status": "error",
                "message": f"Error consultando metadatos: {documents['error']}"
            }
        
        # Formatear resultados
        formatted_docs = []
        for doc in documents:
            formatted_docs.append({
                "display_name": doc['display_name'],
                "version": doc['version'],
                "corpus": doc['corpus_name'],
                "uploaded_at": str(doc['uploaded_at']),
                "uploaded_by": doc['uploaded_by'],
                "description": doc['description'],
                "file_type": doc['file_type'],
                "is_active": doc['is_active'],
            })
        
        return {
            "status": "success",
            "message": f"Se encontraron {len(formatted_docs)} documento(s)",
            "documents": formatted_docs,
            "total": len(formatted_docs)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error obteniendo versiones: {str(e)}"
        }