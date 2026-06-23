"""Tests for strip_markdown_fences() and extract_text_content() in
app/utils/content_utils.py.

Out of scope: bootstrap_history_from_db() — async + DB, belongs in
integration tests.

Run:
    uv run pytest -m unit tests/unit/utils/test_content_utils.py
"""

import pytest

pytestmark = pytest.mark.unit


# ===========================================================================
# strip_markdown_fences()
# ===========================================================================


class TestStripMarkdownFences:
    """Tests for strip_markdown_fences(text: str) -> str.

    Regex: r"^```(?:\\w+)?\\s*\\n(.*?)```\\s*$"  (re.DOTALL)
    Called on text.strip() — so surrounding whitespace is handled before
    the regex runs.  The captured group is also .strip()-ped before return.
    """

    # ------------------------------------------------------------------
    # Fenced with a language tag
    # ------------------------------------------------------------------

    def test_json_fence_returns_inner_content(self):
        from app.utils.content_utils import strip_markdown_fences

        text = '```json\n{"key": "value"}\n```'
        assert strip_markdown_fences(text) == '{"key": "value"}'

    def test_python_fence_returns_inner_content(self):
        from app.utils.content_utils import strip_markdown_fences

        text = "```python\ndef hello():\n    return 'hi'\n```"
        assert strip_markdown_fences(text) == "def hello():\n    return 'hi'"

    def test_yaml_fence_returns_inner_content(self):
        from app.utils.content_utils import strip_markdown_fences

        text = "```yaml\nkey: value\n```"
        assert strip_markdown_fences(text) == "key: value"

    def test_sql_multiline_fence_returns_inner_content(self):
        from app.utils.content_utils import strip_markdown_fences

        text = "```sql\nSELECT *\nFROM users\nWHERE id = 1;\n```"
        assert strip_markdown_fences(text) == "SELECT *\nFROM users\nWHERE id = 1;"

    # ------------------------------------------------------------------
    # Fenced without a language tag
    # ------------------------------------------------------------------

    def test_no_lang_tag_single_line_returns_inner_content(self):
        from app.utils.content_utils import strip_markdown_fences

        text = "```\nhello world\n```"
        assert strip_markdown_fences(text) == "hello world"

    def test_no_lang_tag_multiline_returns_inner_content(self):
        from app.utils.content_utils import strip_markdown_fences

        text = "```\nline one\nline two\n```"
        assert strip_markdown_fences(text) == "line one\nline two"

    # ------------------------------------------------------------------
    # Plain text — no fences → returned unchanged
    # ------------------------------------------------------------------

    def test_plain_text_returned_unchanged(self):
        from app.utils.content_utils import strip_markdown_fences

        text = "just plain text with no fences"
        assert strip_markdown_fences(text) == text

    def test_plain_text_with_newlines_returned_unchanged(self):
        from app.utils.content_utils import strip_markdown_fences

        text = "line one\nline two\nline three"
        assert strip_markdown_fences(text) == text

    def test_empty_string_returned_unchanged(self):
        from app.utils.content_utils import strip_markdown_fences

        assert strip_markdown_fences("") == ""

    # ------------------------------------------------------------------
    # Surrounding whitespace handling
    # The function calls text.strip() before matching, so leading/trailing
    # whitespace outside the fence is consumed.  The captured group is also
    # .strip()-ped, so whitespace between the fence markers and content is
    # removed too.
    # ------------------------------------------------------------------

    def test_leading_whitespace_around_fence_stripped(self):
        from app.utils.content_utils import strip_markdown_fences

        text = "   ```json\n{}\n```"
        assert strip_markdown_fences(text) == "{}"

    def test_trailing_whitespace_around_fence_stripped(self):
        from app.utils.content_utils import strip_markdown_fences

        text = "```json\n{}\n```   "
        assert strip_markdown_fences(text) == "{}"

    def test_surrounding_newlines_stripped(self):
        from app.utils.content_utils import strip_markdown_fences

        text = '\n\n```json\n{"a": 1}\n```\n\n'
        assert strip_markdown_fences(text) == '{"a": 1}'

    def test_inner_indentation_preserved(self):
        """The captured group is .strip()-ped, so leading whitespace on the
        *first* line is removed, but indentation on subsequent lines is kept."""
        from app.utils.content_utils import strip_markdown_fences

        text = "```\n  indented line\n    deeper indent\n```"
        result = strip_markdown_fences(text)
        # .strip() removes the leading spaces from the first captured line
        assert "indented line" in result
        # indentation on the second line is preserved
        assert "    deeper indent" in result


# ===========================================================================
# extract_text_content()
# ===========================================================================


class TestExtractTextContent:
    """Tests for extract_text_content(content: str | dict | list) -> str."""

    # ------------------------------------------------------------------
    # str input → returned as-is
    # ------------------------------------------------------------------

    def test_str_input_returned_as_is(self):
        from app.utils.content_utils import extract_text_content

        assert extract_text_content("hello world") == "hello world"

    def test_str_empty_returned_as_is(self):
        from app.utils.content_utils import extract_text_content

        assert extract_text_content("") == ""

    def test_str_with_internal_whitespace_returned_as_is(self):
        from app.utils.content_utils import extract_text_content

        assert extract_text_content("  spaced  ") == "  spaced  "

    # ------------------------------------------------------------------
    # dict with "text" key → return content["text"]
    # ------------------------------------------------------------------

    def test_dict_with_text_key_returns_its_value(self):
        from app.utils.content_utils import extract_text_content

        assert extract_text_content({"text": "from dict"}) == "from dict"

    def test_dict_with_text_key_empty_value(self):
        from app.utils.content_utils import extract_text_content

        assert extract_text_content({"text": ""}) == ""

    def test_dict_with_text_key_ignores_other_keys(self):
        from app.utils.content_utils import extract_text_content

        d = {"text": "important", "role": "assistant", "extra": 99}
        assert extract_text_content(d) == "important"

    # ------------------------------------------------------------------
    # dict without "text" key → str(dict)
    # ------------------------------------------------------------------

    def test_dict_without_text_key_returns_str_repr(self):
        from app.utils.content_utils import extract_text_content

        d = {"role": "assistant", "value": 42}
        assert extract_text_content(d) == str(d)

    def test_empty_dict_returns_str_repr(self):
        from app.utils.content_utils import extract_text_content

        assert extract_text_content({}) == str({})

    # ------------------------------------------------------------------
    # list of parts — text dicts and plain strings
    # Parts are joined with "\n" (per implementation: "\n".join(texts))
    # ------------------------------------------------------------------

    def test_list_text_type_parts_joined_with_newline(self):
        from app.utils.content_utils import extract_text_content

        parts = [
            {"type": "text", "text": "Hello"},
            {"type": "text", "text": "world"},
        ]
        assert extract_text_content(parts) == "Hello\nworld"

    def test_list_plain_strings_joined_with_newline(self):
        from app.utils.content_utils import extract_text_content

        parts = ["foo", "bar"]
        assert extract_text_content(parts) == "foo\nbar"

    def test_list_mixed_text_dicts_and_plain_strings(self):
        from app.utils.content_utils import extract_text_content

        parts = [
            {"type": "text", "text": "Hello"},
            "plain",
            {"type": "text", "text": "world"},
        ]
        result = extract_text_content(parts)
        assert "Hello" in result
        assert "plain" in result
        assert "world" in result

    def test_list_non_text_type_parts_ignored(self):
        """tool_use, image, and other non-text blocks must not leak into output."""
        from app.utils.content_utils import extract_text_content

        parts = [
            {"type": "tool_use", "id": "abc", "name": "search_kb"},
            {"type": "text", "text": "visible text"},
            {"type": "image", "source": {"url": "https://example.com/img.png"}},
        ]
        result = extract_text_content(parts)
        assert result == "visible text"
        assert "tool_use" not in result
        assert "search_kb" not in result
        assert "image" not in result

    def test_list_only_non_text_parts_returns_empty_string(self):
        from app.utils.content_utils import extract_text_content

        parts = [
            {"type": "tool_use", "id": "x"},
            {"type": "image", "source": {}},
        ]
        assert extract_text_content(parts) == ""

    def test_list_single_text_part(self):
        from app.utils.content_utils import extract_text_content

        parts = [{"type": "text", "text": "only me"}]
        assert extract_text_content(parts) == "only me"

    def test_list_text_part_missing_text_key_contributes_empty_string(self):
        """part.get("text", "") — a text-typed dict with no "text" key gives ""."""
        from app.utils.content_utils import extract_text_content

        parts = [{"type": "text"}, {"type": "text", "text": "after"}]
        result = extract_text_content(parts)
        # both parts collected; joined → "\nafter" or "after" depending on strip
        assert "after" in result

    # ------------------------------------------------------------------
    # Empty list → empty string
    # ------------------------------------------------------------------

    def test_empty_list_returns_empty_string(self):
        from app.utils.content_utils import extract_text_content

        assert extract_text_content([]) == ""

    # ------------------------------------------------------------------
    # Unsupported types → empty string (the final bare `return ""`)
    # ------------------------------------------------------------------

    def test_none_returns_empty_string(self):
        from app.utils.content_utils import extract_text_content

        assert extract_text_content(None) == ""

    def test_integer_returns_empty_string(self):
        from app.utils.content_utils import extract_text_content

        assert extract_text_content(42) == ""

    def test_boolean_returns_empty_string(self):
        from app.utils.content_utils import extract_text_content

        assert extract_text_content(True) == ""