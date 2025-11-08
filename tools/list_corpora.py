

from typing import Dict, List, Union

from vertexai import rag


def list_corpora() -> dict:

    try:
        # Get the list of corpora
        corpora = rag.list_corpora()

        # Process corpus information into a more usable format
        corpus_info: List[Dict[str, Union[str, int]]] = []
        for corpus in corpora:
            corpus_data: Dict[str, Union[str, int]] = {
                "resource_name": corpus.name,  # Full resource name for use with other tools
                "display_name": corpus.display_name,
                "create_time": (
                    str(corpus.create_time) if hasattr(corpus, "create_time") else ""
                ),
                "update_time": (
                    str(corpus.update_time) if hasattr(corpus, "update_time") else ""
                ),
            }

            corpus_info.append(corpus_data)

        return {
            "status": "success",
            "message": f"Found {len(corpus_info)} available corpora",
            "corpora": corpus_info,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error listing corpora: {str(e)}",
            "corpora": [],
        }
