import json
from typing import Any, Dict, List


class StreamingService:
    def __init__(self):
        self.terminal_idx = 1
        self.message_annotations = [
            {
                "type": "TERMINAL_INFO",
                "content": []
            },
            {
                "type": "SOURCES",
                "content": []
            },
            {
                "type": "ANSWER",
                "content": []
            },
            {
                "type": "FURTHER_QUESTIONS",
                "content": []
            }
        ]
    # It is used to send annotations to the frontend
    def _format_annotations(self) -> str:
        """
        Format the annotations as a string
        
        Returns:
            str: The formatted annotations string
        """
        return f'8:{json.dumps(self.message_annotations)}\n'
    
    # It is used to end Streaming
    def format_completion(self, prompt_tokens: int = 156, completion_tokens: int = 204) -> str:
        """
        Format a completion message
        
        Args:
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            
        Returns:
            str: The formatted completion string
        """
        total_tokens = prompt_tokens + completion_tokens
        completion_data = {
            "finishReason": "stop",
            "usage": {
                "promptTokens": prompt_tokens,
                "completionTokens": completion_tokens,
                "totalTokens": total_tokens
            }
        }
        return f'd:{json.dumps(completion_data)}\n' 
    
    def only_update_terminal(self, text: str, message_type: str = "info") -> str:
        self.message_annotations[0]["content"].append({
            "id": self.terminal_idx,
            "text": text,
            "type": message_type
        })
        self.terminal_idx += 1
        return self.message_annotations

    def only_update_sources(self, sources: List[Dict[str, Any]]) -> str:
        self.message_annotations[1]["content"] = sources
        return self.message_annotations
    
    def only_update_answer(self, answer: List[str]) -> str:
        self.message_annotations[2]["content"] = answer
        return self.message_annotations
    
    def only_update_further_questions(self, further_questions: List[Dict[str, Any]]) -> str:
        """
        Update the further questions annotation
        
        Args:
            further_questions: List of further question objects with id and question fields
            
        Returns:
            str: The updated annotations
        """
        self.message_annotations[3]["content"] = further_questions
        return self.message_annotations
    
    