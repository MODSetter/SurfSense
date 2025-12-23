"""
Vercel AI SDK Data Stream Protocol Implementation

This module implements the Vercel AI SDK streaming protocol for use with
@ai-sdk/react's useChat and useCompletion hooks.

Protocol Reference:
- Uses Server-Sent Events (SSE) format
- Requires 'x-vercel-ai-ui-message-stream: v1' header
- Supports text, reasoning, sources, files, tools, data, and error parts
"""

import json
import uuid
from dataclasses import dataclass, field
from typing import Any


def generate_id() -> str:
    """Generate a unique ID for stream parts."""
    return f"msg_{uuid.uuid4().hex}"


@dataclass
class StreamContext:
    """
    Maintains context for streaming operations.
    Tracks active text and reasoning blocks.
    """

    message_id: str = field(default_factory=generate_id)
    active_text_id: str | None = None
    active_reasoning_id: str | None = None
    step_count: int = 0


class VercelStreamingService:
    """
    Implements the Vercel AI SDK Data Stream Protocol.

    This service formats messages according to the SSE-based protocol
    that the AI SDK frontend expects. All messages are formatted as:
        data: {json_object}\n\n

    Usage:
        service = VercelStreamingService()

        # Start a message
        yield service.format_message_start()

        # Stream text content
        text_id = service.generate_text_id()
        yield service.format_text_start(text_id)
        yield service.format_text_delta(text_id, "Hello, ")
        yield service.format_text_delta(text_id, "world!")
        yield service.format_text_end(text_id)

        # Finish the message
        yield service.format_finish()
        yield service.format_done()
    """

    def __init__(self):
        self.context = StreamContext()

    @staticmethod
    def get_response_headers() -> dict[str, str]:
        """
        Get the required HTTP headers for Vercel AI SDK streaming.

        Returns:
            dict: Headers to include in the streaming response
        """
        return {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "x-vercel-ai-ui-message-stream": "v1",
        }

    @staticmethod
    def _format_sse(data: Any) -> str:
        """
        Format data as a Server-Sent Event.

        Args:
            data: The data to format (will be JSON serialized if not a string)

        Returns:
            str: SSE formatted string
        """
        if isinstance(data, str):
            return f"data: {data}\n\n"
        return f"data: {json.dumps(data)}\n\n"

    @staticmethod
    def generate_text_id() -> str:
        """Generate a unique ID for a text block."""
        return f"text_{uuid.uuid4().hex}"

    @staticmethod
    def generate_reasoning_id() -> str:
        """Generate a unique ID for a reasoning block."""
        return f"reasoning_{uuid.uuid4().hex}"

    @staticmethod
    def generate_tool_call_id() -> str:
        """Generate a unique ID for a tool call."""
        return f"call_{uuid.uuid4().hex}"

    # =========================================================================
    # Message Lifecycle Parts
    # =========================================================================

    def format_message_start(self, message_id: str | None = None) -> str:
        """
        Format the start of a new message.

        Args:
            message_id: Optional custom message ID. If not provided, one is generated.

        Returns:
            str: SSE formatted message start part

        Example output:
            data: {"type":"start","messageId":"msg_abc123"}
        """
        if message_id:
            self.context.message_id = message_id
        else:
            self.context.message_id = generate_id()

        return self._format_sse({"type": "start", "messageId": self.context.message_id})

    def format_finish(self) -> str:
        """
        Format the finish message part.

        Returns:
            str: SSE formatted finish part

        Example output:
            data: {"type":"finish"}
        """
        return self._format_sse({"type": "finish"})

    def format_done(self) -> str:
        """
        Format the stream termination marker.

        This should be the last thing sent in a stream.

        Returns:
            str: SSE formatted done marker

        Example output:
            data: [DONE]
        """
        return "data: [DONE]\n\n"

    # =========================================================================
    # Text Parts (start/delta/end pattern)
    # =========================================================================

    def format_text_start(self, text_id: str | None = None) -> str:
        """
        Format the start of a text block.

        Args:
            text_id: Optional custom text block ID. If not provided, one is generated.

        Returns:
            str: SSE formatted text start part

        Example output:
            data: {"type":"text-start","id":"text_abc123"}
        """
        if text_id is None:
            text_id = self.generate_text_id()
        self.context.active_text_id = text_id
        return self._format_sse({"type": "text-start", "id": text_id})

    def format_text_delta(self, text_id: str, delta: str) -> str:
        """
        Format a text delta (incremental content).

        Args:
            text_id: The text block ID
            delta: The incremental text content

        Returns:
            str: SSE formatted text delta part

        Example output:
            data: {"type":"text-delta","id":"text_abc123","delta":"Hello"}
        """
        return self._format_sse({"type": "text-delta", "id": text_id, "delta": delta})

    def format_text_end(self, text_id: str) -> str:
        """
        Format the end of a text block.

        Args:
            text_id: The text block ID

        Returns:
            str: SSE formatted text end part

        Example output:
            data: {"type":"text-end","id":"text_abc123"}
        """
        if self.context.active_text_id == text_id:
            self.context.active_text_id = None
        return self._format_sse({"type": "text-end", "id": text_id})

    def stream_text(self, text_id: str, text: str, chunk_size: int = 10) -> list[str]:
        """
        Convenience method to stream text in chunks.

        Args:
            text_id: The text block ID
            text: The full text to stream
            chunk_size: Size of each chunk (default 10 characters)

        Returns:
            list[str]: List of SSE formatted text delta parts
        """
        parts = []
        for i in range(0, len(text), chunk_size):
            chunk = text[i : i + chunk_size]
            parts.append(self.format_text_delta(text_id, chunk))
        return parts

    # =========================================================================
    # Reasoning Parts (start/delta/end pattern)
    # =========================================================================

    def format_reasoning_start(self, reasoning_id: str | None = None) -> str:
        """
        Format the start of a reasoning block.

        Args:
            reasoning_id: Optional custom reasoning block ID.

        Returns:
            str: SSE formatted reasoning start part

        Example output:
            data: {"type":"reasoning-start","id":"reasoning_abc123"}
        """
        if reasoning_id is None:
            reasoning_id = self.generate_reasoning_id()
        self.context.active_reasoning_id = reasoning_id
        return self._format_sse({"type": "reasoning-start", "id": reasoning_id})

    def format_reasoning_delta(self, reasoning_id: str, delta: str) -> str:
        """
        Format a reasoning delta (incremental reasoning content).

        Args:
            reasoning_id: The reasoning block ID
            delta: The incremental reasoning content

        Returns:
            str: SSE formatted reasoning delta part

        Example output:
            data: {"type":"reasoning-delta","id":"reasoning_abc123","delta":"Let me think..."}
        """
        return self._format_sse(
            {"type": "reasoning-delta", "id": reasoning_id, "delta": delta}
        )

    def format_reasoning_end(self, reasoning_id: str) -> str:
        """
        Format the end of a reasoning block.

        Args:
            reasoning_id: The reasoning block ID

        Returns:
            str: SSE formatted reasoning end part

        Example output:
            data: {"type":"reasoning-end","id":"reasoning_abc123"}
        """
        if self.context.active_reasoning_id == reasoning_id:
            self.context.active_reasoning_id = None
        return self._format_sse({"type": "reasoning-end", "id": reasoning_id})

    # =========================================================================
    # Source Parts
    # =========================================================================

    def format_source_url(
        self, url: str, source_id: str | None = None, title: str | None = None
    ) -> str:
        """
        Format a source URL reference.

        Args:
            url: The source URL
            source_id: Optional source identifier (defaults to URL)
            title: Optional title for the source

        Returns:
            str: SSE formatted source URL part

        Example output:
            data: {"type":"source-url","sourceId":"https://example.com","url":"https://example.com"}
        """
        data: dict[str, Any] = {
            "type": "source-url",
            "sourceId": source_id or url,
            "url": url,
        }
        if title:
            data["title"] = title
        return self._format_sse(data)

    def format_source_document(
        self,
        source_id: str,
        media_type: str = "file",
        title: str | None = None,
        description: str | None = None,
    ) -> str:
        """
        Format a source document reference.

        Args:
            source_id: The source identifier
            media_type: The media type (e.g., "file", "pdf", "document")
            title: Optional title for the document
            description: Optional description

        Returns:
            str: SSE formatted source document part

        Example output:
            data: {"type":"source-document","sourceId":"doc_123","mediaType":"file","title":"Report"}
        """
        data: dict[str, Any] = {
            "type": "source-document",
            "sourceId": source_id,
            "mediaType": media_type,
        }
        if title:
            data["title"] = title
        if description:
            data["description"] = description
        return self._format_sse(data)

    def format_sources(self, sources: list[dict[str, Any]]) -> list[str]:
        """
        Format multiple sources.

        Args:
            sources: List of source objects with 'url', 'title', 'type' fields

        Returns:
            list[str]: List of SSE formatted source parts
        """
        parts = []
        for source in sources:
            url = source.get("url")
            if url:
                parts.append(
                    self.format_source_url(
                        url=url,
                        source_id=source.get("id", url),
                        title=source.get("title"),
                    )
                )
            else:
                parts.append(
                    self.format_source_document(
                        source_id=source.get("id", ""),
                        media_type=source.get("type", "file"),
                        title=source.get("title"),
                        description=source.get("description"),
                    )
                )
        return parts

    # =========================================================================
    # File Part
    # =========================================================================

    def format_file(self, url: str, media_type: str) -> str:
        """
        Format a file reference.

        Args:
            url: The file URL
            media_type: The MIME type (e.g., "image/png", "application/pdf")

        Returns:
            str: SSE formatted file part

        Example output:
            data: {"type":"file","url":"https://example.com/file.png","mediaType":"image/png"}
        """
        return self._format_sse({"type": "file", "url": url, "mediaType": media_type})

    # =========================================================================
    # Custom Data Parts
    # =========================================================================

    def format_data(self, data_type: str, data: Any) -> str:
        """
        Format custom data with a type-specific suffix.

        The type will be prefixed with 'data-' automatically.

        Args:
            data_type: The custom data type suffix (e.g., "weather", "chart")
            data: The data payload

        Returns:
            str: SSE formatted data part

        Example output:
            data: {"type":"data-weather","data":{"location":"SF","temperature":100}}
        """
        return self._format_sse({"type": f"data-{data_type}", "data": data})

    def format_terminal_info(self, text: str, message_type: str = "info") -> str:
        """
        Format terminal info as custom data (SurfSense specific).

        Args:
            text: The terminal message text
            message_type: The message type (info, error, success, warning)

        Returns:
            str: SSE formatted terminal info data part
        """
        return self.format_data("terminal-info", {"text": text, "type": message_type})

    def format_further_questions(self, questions: list[str]) -> str:
        """
        Format further questions as custom data (SurfSense specific).

        Args:
            questions: List of suggested follow-up questions

        Returns:
            str: SSE formatted further questions data part
        """
        return self.format_data("further-questions", {"questions": questions})

    def format_thinking_step(
        self,
        step_id: str,
        title: str,
        status: str = "in_progress",
        items: list[str] | None = None,
    ) -> str:
        """
        Format a thinking step for chain-of-thought display (SurfSense specific).

        Args:
            step_id: Unique identifier for the step
            title: The step title (e.g., "Analyzing your request")
            status: Step status - "pending", "in_progress", or "completed"
            items: Optional list of sub-items/details for this step

        Returns:
            str: SSE formatted thinking step data part
        """
        return self.format_data(
            "thinking-step",
            {
                "id": step_id,
                "title": title,
                "status": status,
                "items": items or [],
            },
        )

    # =========================================================================
    # Error Part
    # =========================================================================

    def format_error(self, error_text: str) -> str:
        """
        Format an error message.

        Args:
            error_text: The error message text

        Returns:
            str: SSE formatted error part

        Example output:
            data: {"type":"error","errorText":"Something went wrong"}
        """
        return self._format_sse({"type": "error", "errorText": error_text})

    # =========================================================================
    # Tool Parts
    # =========================================================================

    def format_tool_input_start(self, tool_call_id: str, tool_name: str) -> str:
        """
        Format the start of tool input streaming.

        Args:
            tool_call_id: The unique tool call identifier
            tool_name: The name of the tool being called

        Returns:
            str: SSE formatted tool input start part

        Example output:
            data: {"type":"tool-input-start","toolCallId":"call_abc123","toolName":"getWeather"}
        """
        return self._format_sse(
            {
                "type": "tool-input-start",
                "toolCallId": tool_call_id,
                "toolName": tool_name,
            }
        )

    def format_tool_input_delta(self, tool_call_id: str, input_text_delta: str) -> str:
        """
        Format incremental tool input.

        Args:
            tool_call_id: The tool call identifier
            input_text_delta: The incremental input text

        Returns:
            str: SSE formatted tool input delta part

        Example output:
            data: {"type":"tool-input-delta","toolCallId":"call_abc123","inputTextDelta":"San Fran"}
        """
        return self._format_sse(
            {
                "type": "tool-input-delta",
                "toolCallId": tool_call_id,
                "inputTextDelta": input_text_delta,
            }
        )

    def format_tool_input_available(
        self, tool_call_id: str, tool_name: str, input_data: dict[str, Any]
    ) -> str:
        """
        Format the completion of tool input.

        Args:
            tool_call_id: The tool call identifier
            tool_name: The name of the tool
            input_data: The complete tool input parameters

        Returns:
            str: SSE formatted tool input available part

        Example output:
            data: {"type":"tool-input-available","toolCallId":"call_abc123","toolName":"getWeather","input":{"city":"SF"}}
        """
        return self._format_sse(
            {
                "type": "tool-input-available",
                "toolCallId": tool_call_id,
                "toolName": tool_name,
                "input": input_data,
            }
        )

    def format_tool_output_available(self, tool_call_id: str, output: Any) -> str:
        """
        Format tool execution output.

        Args:
            tool_call_id: The tool call identifier
            output: The tool execution result

        Returns:
            str: SSE formatted tool output available part

        Example output:
            data: {"type":"tool-output-available","toolCallId":"call_abc123","output":{"weather":"sunny"}}
        """
        return self._format_sse(
            {
                "type": "tool-output-available",
                "toolCallId": tool_call_id,
                "output": output,
            }
        )

    # =========================================================================
    # Step Parts
    # =========================================================================

    def format_start_step(self) -> str:
        """
        Format the start of a step (one LLM API call).

        Returns:
            str: SSE formatted start step part

        Example output:
            data: {"type":"start-step"}
        """
        self.context.step_count += 1
        return self._format_sse({"type": "start-step"})

    def format_finish_step(self) -> str:
        """
        Format the completion of a step.

        This is necessary for correctly processing multiple stitched
        assistant calls, e.g., when calling tools in the backend.

        Returns:
            str: SSE formatted finish step part

        Example output:
            data: {"type":"finish-step"}
        """
        return self._format_sse({"type": "finish-step"})

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    def stream_full_text(self, text: str, chunk_size: int = 10) -> list[str]:
        """
        Convenience method to stream a complete text block.

        Generates: text-start, text-deltas, text-end

        Args:
            text: The full text to stream
            chunk_size: Size of each chunk

        Returns:
            list[str]: List of all SSE formatted parts
        """
        text_id = self.generate_text_id()
        parts = [self.format_text_start(text_id)]
        parts.extend(self.stream_text(text_id, text, chunk_size))
        parts.append(self.format_text_end(text_id))
        return parts

    def stream_full_reasoning(self, reasoning: str, chunk_size: int = 20) -> list[str]:
        """
        Convenience method to stream a complete reasoning block.

        Generates: reasoning-start, reasoning-deltas, reasoning-end

        Args:
            reasoning: The full reasoning text
            chunk_size: Size of each chunk

        Returns:
            list[str]: List of all SSE formatted parts
        """
        reasoning_id = self.generate_reasoning_id()
        parts = [self.format_reasoning_start(reasoning_id)]
        for i in range(0, len(reasoning), chunk_size):
            chunk = reasoning[i : i + chunk_size]
            parts.append(self.format_reasoning_delta(reasoning_id, chunk))
        parts.append(self.format_reasoning_end(reasoning_id))
        return parts

    def create_complete_response(
        self,
        text: str,
        sources: list[dict[str, Any]] | None = None,
        reasoning: str | None = None,
        further_questions: list[str] | None = None,
        chunk_size: int = 10,
    ) -> list[str]:
        """
        Create a complete streaming response with all parts.

        This is a convenience method that generates a full response
        including message start, optional reasoning, text, sources,
        further questions, and finish markers.

        Args:
            text: The main response text
            sources: Optional list of source references
            reasoning: Optional reasoning/thinking content
            further_questions: Optional follow-up questions
            chunk_size: Size of text chunks

        Returns:
            list[str]: List of all SSE formatted parts in correct order
        """
        parts = []

        # Start message
        parts.append(self.format_message_start())
        parts.append(self.format_start_step())

        # Reasoning (if provided)
        if reasoning:
            parts.extend(self.stream_full_reasoning(reasoning))

        # Sources (before main text)
        if sources:
            parts.extend(self.format_sources(sources))

        # Main text content
        parts.extend(self.stream_full_text(text, chunk_size))

        # Further questions (if provided)
        if further_questions:
            parts.append(self.format_further_questions(further_questions))

        # Finish
        parts.append(self.format_finish_step())
        parts.append(self.format_finish())
        parts.append(self.format_done())

        return parts

    def reset(self) -> None:
        """Reset the streaming context for a new message."""
        self.context = StreamContext()
