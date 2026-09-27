"""Chroma wrapper: two persistent collections.

- mod_files:    one entry per moddable file, built by index_mod_files.py
- known_issues: one entry per issue (open or resolved), grows over time as
                reports come in and as merged tickets feed the learning loop
"""
import chromadb


class Store:
    def __init__(self, persist_dir: str):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.mod_files = self.client.get_or_create_collection("mod_files")
        self.known_issues = self.client.get_or_create_collection("known_issues")

    def query(self, collection, embedding: list[float], k: int = 5) -> list[dict]:
        res = collection.query(query_embeddings=[embedding], n_results=k)
        if not res["ids"][0]:
            return []
        return [
            {
                "id": res["ids"][0][i],
                "document": res["documents"][0][i],
                "metadata": res["metadatas"][0][i],
                "distance": res["distances"][0][i],
            }
            for i in range(len(res["ids"][0]))
        ]

    def upsert_issue(self, id: str, embedding: list[float], text: str, metadata: dict):
        self.known_issues.upsert(ids=[id], embeddings=[embedding], documents=[text], metadatas=[metadata])

    def upsert_file(self, id: str, embedding: list[float], summary: str, path: str):
        self.mod_files.upsert(ids=[id], embeddings=[embedding], documents=[summary], metadatas=[{"path": path}])
