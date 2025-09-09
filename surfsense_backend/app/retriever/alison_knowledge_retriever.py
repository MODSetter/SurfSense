import json
import os
from app.config import config

class AlisonKnowledgeRetriever:
    def __init__(self, db_session=None):
        self.db_session = db_session
        self.faq_path = os.path.join(config.BASE_DIR, "app", "alison_docs", "classroom_faq.json")
        with open(self.faq_path, "r") as f:
            self.faq_data = json.load(f)

    async def hybrid_search(self, query_text: str, top_k: int) -> list:
        # Simple keyword search on the issue field
        keywords = query_text.lower().split()
        for entry in self.faq_data:
            if any(keyword in entry["issue"].lower() for keyword in keywords):
                return [{"content": "\n".join(entry["resolution"])}]
        return []
