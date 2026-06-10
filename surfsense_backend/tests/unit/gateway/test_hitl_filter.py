from app.gateway.hitl_filter import filter_hitl_tools


class Tool:
    def __init__(self, name: str) -> None:
        self.name = name


def test_filter_hitl_tools_removes_known_approval_tools():
    tools = [Tool("delete_document"), Tool("search"), "send_email", "summarize"]

    filtered = filter_hitl_tools(tools)

    assert [getattr(tool, "name", tool) for tool in filtered] == ["search", "summarize"]
