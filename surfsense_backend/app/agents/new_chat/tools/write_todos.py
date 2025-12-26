"""
Write todos tool for the SurfSense agent.

This module provides a tool for creating and displaying a planning/todo list
in the chat UI. It helps the agent break down complex tasks into steps.
"""

from typing import Any, Literal

from langchain_core.tools import tool


def create_write_todos_tool():
    """
    Factory function to create the write_todos tool.

    Returns:
        A configured tool function for writing todos/plans.
    """

    @tool
    async def write_todos(
        todos: list[dict[str, Any]],
        title: str = "Planning Approach",
        description: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a planning/todo list to break down a complex task.

        Use this tool when you need to plan your approach to a complex task
        or show the user a step-by-step breakdown of what you'll do.

        This displays a visual plan with:
        - Progress tracking (X of Y complete)
        - Status indicators (pending, in progress, completed, cancelled)
        - Expandable details for each step

        Args:
            todos: List of todo items. Each item should have:
                - id: Unique identifier for the todo
                - content: Description of the task
                - status: One of "pending", "in_progress", "completed", "cancelled"
            title: Title for the plan (default: "Planning Approach")
            description: Optional description providing context

        Returns:
            A dictionary containing the plan data for the UI to render.

        Example:
            write_todos(
                title="Implementation Plan",
                description="Steps to add the new feature",
                todos=[
                    {"id": "1", "content": "Analyze requirements", "status": "completed"},
                    {"id": "2", "content": "Design solution", "status": "in_progress"},
                    {"id": "3", "content": "Write code", "status": "pending"},
                    {"id": "4", "content": "Add tests", "status": "pending"},
                ]
            )
        """
        # Generate a unique plan ID
        import uuid

        plan_id = f"plan-{uuid.uuid4().hex[:8]}"

        # Transform todos to the expected format for the UI
        formatted_todos = []
        for i, todo in enumerate(todos):
            todo_id = todo.get("id", f"todo-{i}")
            content = todo.get("content", "")
            status = todo.get("status", "pending")

            # Validate status
            valid_statuses = ["pending", "in_progress", "completed", "cancelled"]
            if status not in valid_statuses:
                status = "pending"

            formatted_todos.append(
                {
                    "id": todo_id,
                    "label": content,
                    "status": status,
                }
            )

        return {
            "id": plan_id,
            "title": title,
            "description": description,
            "todos": formatted_todos,
        }

    return write_todos

