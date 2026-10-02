"""The mind map reply's shape, enforced as a grammar while the model writes.

Every tier asks for a tree two or three levels deep, so the three levels are
written out rather than recursive: no `$ref` for the grammar to resolve. A leaf
declares no children, and llama.cpp closes an object to the properties it
declares, so the tree cannot grow a fourth. The branch count stays the
prompt's to ask for and the builder's to cap.
"""

_LEAF = {
    "type": "object",
    "properties": {"label": {"type": "string"}},
    "required": ["label"],
}

_CHILD = {
    "type": "object",
    "properties": {
        "label": {"type": "string"},
        "children": {"type": "array", "items": _LEAF},
    },
    "required": ["label"],
}

_BRANCH = {
    "type": "object",
    "properties": {
        "label": {"type": "string"},
        "children": {"type": "array", "items": _CHILD},
    },
    "required": ["label"],
}

REPLY = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "nodes": {"type": "array", "items": _BRANCH},
    },
    "required": ["title", "nodes"],
}
