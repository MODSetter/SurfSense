import json
from typing import List, Dict, Any, Generator

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
            }
        ]
    
    def add_terminal_message(self, text: str, message_type: str = "info") -> str:
        """
        Add a terminal message to the annotations and return the formatted response
        
        Args:
            text: The message text
            message_type: The message type (info, success, error)
            
        Returns:
            str: The formatted response string
        """
        self.message_annotations[0]["content"].append({
            "id": self.terminal_idx,
            "text": text,
            "type": message_type
        })
        self.terminal_idx += 1
        return self._format_annotations()
    
    def update_sources(self, sources: List[Dict[str, Any]]) -> str:
        """
        Update the sources in the annotations and return the formatted response
        
        Args:
            sources: List of source objects
            
        Returns:
            str: The formatted response string
        """
        self.message_annotations[1]["content"] = sources
        return self._format_annotations()
    
    def update_answer(self, answer_content: List[str]) -> str:
        """
        Update the answer in the annotations and return the formatted response
        
        Args:
            answer_content: The answer content as a list of strings
            
        Returns:
            str: The formatted response string
        """
        self.message_annotations[2] = {
            "type": "ANSWER",
            "content": answer_content
        }
        return self._format_annotations()
    
    def _format_annotations(self) -> str:
        """
        Format the annotations as a string
        
        Returns:
            str: The formatted annotations string
        """
        return f'8:{json.dumps(self.message_annotations)}\n'
    
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