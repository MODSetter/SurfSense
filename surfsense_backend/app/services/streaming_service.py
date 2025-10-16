import json
from typing import Any


class StreamingService:
    def __init__(self):
        self.terminal_idx = 1
        self.message_annotations = [
            {"type": "TERMINAL_INFO", "content": []},
            {"type": "SOURCES", "content": []},
            {"type": "ANSWER", "content": []},
            {"type": "FURTHER_QUESTIONS", "content": []},
        ]

    # DEPRECATED: This sends the full annotation array every time (inefficient)
    def _format_annotations(self) -> str:
        """
        Format the annotations as a string

        DEPRECATED: This method sends the full annotation state every time.
        Use the delta formatters instead for optimal streaming.

        Returns:
            str: The formatted annotations string
        """
        return f"8:{json.dumps(self.message_annotations)}\n"

    def format_terminal_info_delta(self, text: str, message_type: str = "info") -> str:
        """
        Format a single terminal info message as a delta annotation

        Args:
            text: The terminal message text
            message_type: The message type (info, error, success, etc.)

        Returns:
            str: The formatted annotation delta string
        """
        message = {"id": self.terminal_idx, "text": text, "type": message_type}
        self.terminal_idx += 1

        # Update internal state for reference
        self.message_annotations[0]["content"].append(message)

        # Return only the delta annotation
        annotation = {"type": "TERMINAL_INFO", "data": message}
        return f"8:[{json.dumps(annotation)}]\n"

    def format_sources_delta(self, sources: list[dict[str, Any]]) -> str:
        """
        Format sources as a delta annotation

        Args:
            sources: List of source objects

        Returns:
            str: The formatted annotation delta string
        """
        # Update internal state
        self.message_annotations[1]["content"] = sources

        # Return only the delta annotation
        nodes = []

        for group in sources:
            for source in group.get("sources", []):
                node = {
                    "id": str(source.get("id", "")),
                    "text": source.get("description", "").strip(),
                    "url": source.get("url", ""),
                    "metadata": {
                        "title": source.get("title", ""),
                        "source_type": group.get("type", ""),
                        "group_name": group.get("name", ""),
                    },
                }
                nodes.append(node)

        annotation = {"type": "sources", "data": {"nodes": nodes}}
        return f"8:[{json.dumps(annotation)}]\n"

    def format_answer_delta(self, answer_chunk: str) -> str:
        """
        Format a single answer chunk as a delta annotation

        Args:
            answer_chunk: The new answer chunk to add

        Returns:
            str: The formatted annotation delta string
        """
        # Update internal state by appending the chunk
        if isinstance(self.message_annotations[2]["content"], list):
            self.message_annotations[2]["content"].append(answer_chunk)
        else:
            self.message_annotations[2]["content"] = [answer_chunk]

        # Return only the delta annotation with the new chunk
        annotation = {"type": "ANSWER", "content": [answer_chunk]}
        return f"8:[{json.dumps(annotation)}]\n"

    def format_answer_annotation(self, answer_lines: list[str]) -> str:
        """
        Format the complete answer as a replacement annotation

        Args:
            answer_lines: Complete list of answer lines

        Returns:
            str: The formatted annotation string
        """
        # Update internal state
        self.message_annotations[2]["content"] = answer_lines

        # Return the full answer annotation
        annotation = {"type": "ANSWER", "content": answer_lines}
        return f"8:[{json.dumps(annotation)}]\n"

    def format_further_questions_delta(
        self, further_questions: list[dict[str, Any]]
    ) -> str:
        """
        Format further questions as a delta annotation

        Args:
            further_questions: List of further question objects

        Returns:
            str: The formatted annotation delta string
        """
        # Update internal state
        self.message_annotations[3]["content"] = further_questions

        # Return only the delta annotation
        annotation = {
            "type": "FURTHER_QUESTIONS",
            "data": [
                question.get("question", "")
                for question in further_questions
                if question.get("question", "") != ""
            ],
        }
        return f"8:[{json.dumps(annotation)}]\n"

    def format_text_chunk(self, text: str) -> str:
        """
        Format a text chunk using the text stream part

        Args:
            text: The text chunk to stream

        Returns:
            str: The formatted text part string
        """
        return f"0:{json.dumps(text)}\n"

    def format_error(self, error_message: str) -> str:
        """
        Format an error using the error stream part

        Args:
            error_message: The error message

        Returns:
            str: The formatted error part string
        """
        return f"3:{json.dumps(error_message)}\n"

    def format_completion(
        self, prompt_tokens: int = 156, completion_tokens: int = 204
    ) -> str:
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
                "totalTokens": total_tokens,
            },
        }
        return f"d:{json.dumps(completion_data)}\n"
