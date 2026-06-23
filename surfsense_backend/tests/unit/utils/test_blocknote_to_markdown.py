"""Tests for the blocknote_to_markdown conversion module.

This module contains comprehensive unit tests for the blocknote_to_markdown function,
covering all block types, inline styles, lists, tables, images, links, nested content,
and edge cases.
"""

import pytest

from app.utils.blocknote_to_markdown import blocknote_to_markdown

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Headings (levels 1 to 6, and clamping for >6 / <1)
# ---------------------------------------------------------------------------


class TestHeadingsLevelsAndClamping:
    """Test heading conversion with various levels and clamping behavior."""

    def test_heading_level_less_than_1(self):
        """Heading level < 1 should be clamped to H1 (#)."""

        test_block = {
            "type": "heading",
            "props": {"level": 0},
            "content": [{"type": "text", "text": "My Title"}],
        }

        assert blocknote_to_markdown(test_block) == "# My Title"

    def test_heading_level_1(self):
        """Heading level 1 should render as H1 (#)."""

        test_block = {
            "type": "heading",
            "props": {"level": 1},
            "content": [{"type": "text", "text": "My Title"}],
        }

        assert blocknote_to_markdown(test_block) == "# My Title"

    def test_heading_level_2(self):
        """Heading level 2 should render as H2 (##)."""

        test_block = {
            "type": "heading",
            "props": {"level": 2},
            "content": [{"type": "text", "text": "My Title"}],
        }

        assert blocknote_to_markdown(test_block) == "## My Title"

    def test_heading_level_3(self):
        """Heading level 3 should render as H3 (###)."""

        test_block = {
            "type": "heading",
            "props": {"level": 3},
            "content": [{"type": "text", "text": "My Title"}],
        }

        assert blocknote_to_markdown(test_block) == "### My Title"

    def test_heading_level_4(self):
        """Heading level 4 should render as H4 (####)."""

        test_block = {
            "type": "heading",
            "props": {"level": 4},
            "content": [{"type": "text", "text": "My Title"}],
        }

        assert blocknote_to_markdown(test_block) == "#### My Title"

    def test_heading_level_5(self):
        """Heading level 5 should render as H5 (#####)."""

        test_block = {
            "type": "heading",
            "props": {"level": 5},
            "content": [{"type": "text", "text": "My Title"}],
        }

        assert blocknote_to_markdown(test_block) == "##### My Title"

    def test_heading_level_6(self):
        """Heading level 6 should render as H6 (######)."""

        test_block = {
            "type": "heading",
            "props": {"level": 6},
            "content": [{"type": "text", "text": "My Title"}],
        }

        assert blocknote_to_markdown(test_block) == "###### My Title"

    def test_heading_level_greater_than_6(self):
        """Heading level > 6 should be clamped to H6 (######)."""

        test_block = {
            "type": "heading",
            "props": {"level": 6},
            "content": [{"type": "text", "text": "My Title"}],
        }

        assert blocknote_to_markdown(test_block) == "###### My Title"


# ---------------------------------------------------------------------------
# Inline styles: bold, italic, code, strikethrough
# ---------------------------------------------------------------------------


class TestInlineStyles:
    """Test inline text styling conversion."""

    def test_bold_inline_style(self):
        """Bold text should be wrapped in double asterisks (**)."""

        test_block = {
            "type": "paragraph",
            "styles": {"bold": True},
            "content": [{"type": "text", "text": "Hello World!", "styles": {}}],
        }

        assert blocknote_to_markdown(test_block) == "**Hello World!**"

    def test_italic_inline_style(self):
        """Italic text should be wrapped in single asterisks (*)."""

        test_block = {
            "type": "paragraph",
            "styles": {"italic": True},
            "content": [{"type": "text", "text": "Hello World!", "styles": {}}],
        }

        assert blocknote_to_markdown(test_block) == "*Hello World!*"

    def test_code_inline_style(self):
        """Code text should be wrapped in backticks (`)."""

        test_block = {
            "type": "paragraph",
            "styles": {"code": True},
            "content": [{"type": "text", "text": "Hello World!", "styles": {}}],
        }

        assert blocknote_to_markdown(test_block) == "`Hello World!`"

    def test_strikethrough_inline_style(self):
        """Strikethrough text should be wrapped in double tildes (~~)."""

        test_block = {
            "type": "paragraph",
            "styles": {"strikethrough": True},
            "content": [{"type": "text", "text": "Hello World!", "styles": {}}],
        }

        assert blocknote_to_markdown(test_block) == "~~Hello World!~~"


# ---------------------------------------------------------------------------
# Lists: bullet, numbered (incl. props.start and counter reset), checklist (checked/unchecked)
# ---------------------------------------------------------------------------


class TestBulletAndNumberLists:
    """Test bullet and numbered list conversion."""

    def test_bullet_list_item(self):
        """Bullet list items should render with dash (-) prefix."""

        test_block = [
            {"type": "bulletListItem", "content": [{"type": "text", "text": "First"}]},
            {"type": "bulletListItem", "content": [{"type": "text", "text": "Second"}]},
        ]

        assert blocknote_to_markdown(test_block) == "- First\n- Second"

    def test_numbered_list_item(self):
        """Numbered list items should auto-increment from 1."""

        test_block = [
            {
                "type": "numberedListItem",
                "content": [{"type": "text", "text": "First"}],
            },
            {
                "type": "numberedListItem",
                "content": [{"type": "text", "text": "Second"}],
            },
        ]

        assert blocknote_to_markdown(test_block) == "1. First\n2. Second"

    def test_numbered_list_item_with_prop_start(self):
        """Numbered list with props.start should begin at specified number."""

        test_block = [
            {
                "type": "numberedListItem",
                "props": {"start": 5},
                "content": [{"type": "text", "text": "First"}],
            },
            {
                "type": "numberedListItem",
                "content": [{"type": "text", "text": "Second"}],
            },
        ]

        assert blocknote_to_markdown(test_block) == "5. First\n6. Second"

    def test_numbered_list_item_with_counter_reset(self):
        """Multiple numbered lists with different start values should reset counters."""

        test_block = [
            {
                "type": "numberedListItem",
                "content": [{"type": "text", "text": "First"}],
            },
            {
                "type": "numberedListItem",
                "content": [{"type": "text", "text": "Second"}],
            },
            {
                "type": "numberedListItem",
                "props": {"start": 5},
                "content": [{"type": "text", "text": "Third"}],
            },
        ]

        assert blocknote_to_markdown(test_block) == "1. First\n2. Second\n5. Third"


class TestCheckedAndUncheckedChecklist:
    """Test checklist item conversion with checked/unchecked states."""

    def test_checked_list_item(self):
        """Checked checklist item should render with [x]."""

        test_block = {
            "type": "checkListItem",
            "props": {"checked": True},
            "content": [{"type": "text", "text": "Finish implementing test modules"}],
        }

        assert (
            blocknote_to_markdown(test_block)
            == "- [x] Finish implementing test modules"
        )

    def test_unchecked_list_item(self):
        """Unchecked checklist item should render with [ ]."""

        test_block = {
            "type": "checkListItem",
            "props": {"checked": False},
            "content": [{"type": "text", "text": "Finish implementing test modules"}],
        }

        assert (
            blocknote_to_markdown(test_block)
            == "- [ ] Finish implementing test modules"
        )


# ---------------------------------------------------------------------------
# Code blocks (with/without language)
# ---------------------------------------------------------------------------


class TestCodeBlocksWithOrWithoutLanguage:
    """Test code block conversion with optional language tags."""

    def test_code_block_without_language(self):
        """Code block without language should render with empty fence (```)."""

        test_block = {
            "type": "codeBlock",
            "content": [{"type": "text", "text": "print('hi')"}],
        }

        assert blocknote_to_markdown(test_block) == "```\nprint('hi')\n```"

    def test_code_block_with_language(self):
        """Code block with language should render fence with language tag."""

        test_block = {
            "type": "codeBlock",
            "props": {"language": "Python"},
            "content": [{"type": "text", "text": "print('hi')"}],
        }

        assert blocknote_to_markdown(test_block) == "```Python\nprint('hi')\n```"


# ---------------------------------------------------------------------------
# Tables (both dict and list row shapes)
# ---------------------------------------------------------------------------


def test_tables_dict_row_shape():
    """Table with dict row shape should render with header separator."""

    test_block = {
        "type": "table",
        "content": {
            "rows": [
                {"cells": ["Name", "Age", "City"]},
                {"cells": ["Alice", "25", "NYC"]},
                {"cells": ["Bob", "30", "LA"]},
            ]
        },
    }

    assert (
        blocknote_to_markdown(test_block)
        == "| Name | Age | City |\n| --- | --- | --- |\n| Alice | 25 | NYC |\n| Bob | 30 | LA |"
    )


def test_tables_list_row_shape():
    """Table with list row shape should render with header separator."""
    test_block = {
        "type": "table",
        "content": [
            {"cells": ["Header1", "Header2"]},
            {"cells": ["Data1", "Data2"]},
            {"cells": ["Data3", "Data4"]},
        ],
    }

    assert (
        blocknote_to_markdown(test_block)
        == "| Header1 | Header2 |\n| --- | --- |\n| Data1 | Data2 |\n| Data3 | Data4 |"
    )


# ---------------------------------------------------------------------------
# Images and links
# ---------------------------------------------------------------------------


def test_image_block_input():
    """Image block should render as markdown image syntax ![caption](url)."""

    test_block = {
        "type": "image",
        "props": {"url": "https://example.com/pic.jpg", "caption": "A picture"},
    }

    assert (
        blocknote_to_markdown(test_block) == "![A picture](https://example.com/pic.jpg)"
    )


def test_link_block_input_with_text():
    """Link with content should render as [text](href)."""

    test_block = {
        "type": "paragraph",
        "content": [
            {
                "type": "link",
                "href": "https://example.com",
                "content": [{"type": "text", "text": "Click here"}],
            }
        ],
    }

    assert blocknote_to_markdown(test_block) == "[Click here](https://example.com)"


def test_link_block_input_without_text():
    """Link without content should use href as link text."""

    test_block = {
        "type": "paragraph",
        "content": [{"type": "link", "href": "https://example.com"}],
    }

    assert (
        blocknote_to_markdown(test_block)
        == "[https://example.com](https://example.com)"
    )


# ---------------------------------------------------------------------------
# Nested children (indentation)
# ---------------------------------------------------------------------------


def test_nested_children_indentation():
    """Nested list items should be indented with 2 spaces per level."""

    test_block = {
        "type": "bulletListItem",
        "content": [{"type": "text", "text": "Parent"}],
        "children": [
            {
                "type": "bulletListItem",
                "content": [{"type": "text", "text": "Child 1"}],
            },
            {
                "type": "bulletListItem",
                "content": [{"type": "text", "text": "Child 2"}],
            },
            {
                "type": "bulletListItem",
                "content": [{"type": "text", "text": "Child 3"}],
            },
        ],
    }
    prefix = "  "

    assert (
        blocknote_to_markdown(test_block)
        == f"- Parent\n{prefix}- Child 1\n{prefix}- Child 2\n{prefix}- Child 3"
    )


def test_deep_nested_children_indentation():
    """Deeply nested items (3+ levels) should accumulate indentation."""

    test_block = {
        "type": "bulletListItem",
        "content": [{"type": "text", "text": "Parent"}],
        "children": [
            {
                "type": "bulletListItem",
                "content": [{"type": "text", "text": "Child 1"}],
                "children": [
                    {
                        "type": "bulletListItem",
                        "content": [{"type": "text", "text": "Child 2"}],
                        "children": [
                            {
                                "type": "bulletListItem",
                                "content": [{"type": "text", "text": "Child 3"}],
                            }
                        ],
                    }
                ],
            }
        ],
    }

    prefix = "  "

    assert (
        blocknote_to_markdown(test_block)
        == f"- Parent\n{prefix}- Child 1\n{prefix * 2}- Child 2\n{prefix * 3}- Child 3"
    )


def test_mixed_deep_nested_children_indentation():
    """Mixed block types in deep nesting should preserve indentation."""

    test_block = {
        "type": "bulletListItem",
        "content": [{"type": "text", "text": "Parent"}],
        "children": [
            {
                "type": "bulletListItem",
                "content": [{"type": "text", "text": "Child 1"}],
                "children": [
                    {
                        "type": "numberedListItem",
                        "content": [{"type": "text", "text": "Nested Child 1"}],
                        "children": [
                            {
                                "type": "numberedListItem",
                                "content": [{"type": "text", "text": "Nested Child 2"}],
                            }
                        ],
                    }
                ],
            },
            {
                "type": "bulletListItem",
                "content": [{"type": "text", "text": "Child 2"}],
            },
            {
                "type": "bulletListItem",
                "content": [{"type": "text", "text": "Child 3"}],
            },
        ],
    }

    prefix = "  "

    assert (
        blocknote_to_markdown(test_block)
        == f"- Parent\n{prefix}- Child 1\n{prefix * 2}1. Nested Child 1\n{prefix * 3}2. Nested Child 2\n{prefix}- Child 2\n{prefix}- Child 3"
    )


# ---------------------------------------------------------------------------
# Edge cases: None, empty list, single dict input, unknown block type
# ---------------------------------------------------------------------------


def test_none_input():
    """None input should return None."""

    test_block = None

    assert blocknote_to_markdown(test_block) is None


def test_empty_list_input():
    """Empty list input should return None."""

    test_block = []

    assert blocknote_to_markdown(test_block) is None


def test_single_dict_input():
    """Single dict block should be processed normally."""

    test_block = {"type": "paragraph", "content": [{"type": "text", "text": "Hello"}]}

    assert blocknote_to_markdown(test_block) == "Hello"


def test_unknown_block_type_with_content():
    """Unknown block type with content should extract and render the text."""

    test_block = {
        "type": "customBlockType",
        "content": [{"type": "text", "text": "Some content"}],
    }

    assert blocknote_to_markdown(test_block) == "Some content"


def test_unknown_block_type_with_no_content():
    """Unknown block type without content should return None."""

    test_block = {"type": "customBlockType"}

    assert blocknote_to_markdown(test_block) is None
