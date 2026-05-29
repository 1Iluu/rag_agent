import os
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

# Configuración de la base de datos (compatible con tu Spring Boot)
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "RAGDATABASE"),  
    "user": os.getenv("DB_USER", "postgres"),        
    "password": os.getenv("DB_PASSWORD", "1999"),     
}


@contextmanager
def get_db_connection():
    """Context manager para manejar conexiones a la base de datos."""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()


def save_document_metadata(
    rag_file_name: str,
    corpus_name: str,
    display_name: str,
    version: str,
    file_path: str,
    uploaded_by: str,
    description: Optional[str] = None,
    file_type: Optional[str] = None,
    tags: Optional[list] = None,
) -> dict:
    """
    Guarda los metadatos de un documento en PostgreSQL.
    
    Returns:
        dict con status y mensaje
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                INSERT INTO rag_document_metadata 
                (rag_file_name, corpus_name, display_name, version, description, 
                 file_path, uploaded_by, file_type, tags)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (rag_file_name) 
                DO UPDATE SET 
                    version = EXCLUDED.version,
                    description = EXCLUDED.description,
                    uploaded_at = CURRENT_TIMESTAMP
                RETURNING id
            """
            
            cursor.execute(query, (
                rag_file_name,
                corpus_name,
                display_name,
                version,
                description,
                file_path,
                uploaded_by,
                file_type,
                tags
            ))
            
            result = cursor.fetchone()
            return {
                "status": "success",
                "message": f"Metadata saved successfully (ID: {result[0]})",
                "metadata_id": result[0]
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error saving metadata: {str(e)}"
        }


def get_document_metadata(corpus_name: Optional[str] = None, version: Optional[str] = None):
    """Obtiene metadatos filtrados por corpus y/o versión."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            query = "SELECT * FROM rag_document_metadata WHERE is_active = TRUE"
            params = []
            
            if corpus_name:
                query += " AND corpus_name = %s"
                params.append(corpus_name)
            
            if version:
                query += " AND version = %s"
                params.append(version)
            
            query += " ORDER BY uploaded_at DESC"
            
            cursor.execute(query, params)
            return cursor.fetchall()
            
    except Exception as e:
        return {"error": str(e)}


def mark_document_inactive(rag_file_name: str):
    """Marca un documento como inactivo (soft delete)."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE rag_document_metadata SET is_active = FALSE WHERE rag_file_name = %s",
                (rag_file_name,)
            )
            return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}