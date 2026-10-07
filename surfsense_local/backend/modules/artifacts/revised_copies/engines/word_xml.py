"""WordprocessingML names the Word engine reads and writes (ECMA-376 Part 1, section 17)."""

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
OFFICE_DOCUMENT_REL = f"{REL}/officeDocument"
COMMENTS_REL = f"{REL}/comments"
STYLES_REL = f"{REL}/styles"
COMMENTS_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"
)
# Parts that hold comment metadata keyed by the comments' paragraphs.
COMMENTS_EXTENDED_REL = (
    "http://schemas.microsoft.com/office/2011/relationships/commentsExtended"
)
COMMENTS_IDS_REL = (
    "http://schemas.microsoft.com/office/2016/09/relationships/commentsIds"
)
COMMENTS_EXTENSIBLE_REL = (
    "http://schemas.microsoft.com/office/2018/08/relationships/commentsExtensible"
)
# Stories accept and reject reach besides the body.
STORY_RELS = tuple(
    f"{REL}/{kind}"
    for kind in ("header", "footer", "footnotes", "endnotes", "comments")
)


def w(tag: str) -> str:
    return f"{{{W}}}{tag}"


def make(tag: str, **attrs: str) -> etree._Element:
    element = etree.Element(tag if tag.startswith("{") else w(tag))
    for name, value in attrs.items():
        element.set(w(name), value)
    return element


P, R, T, TAB = w("p"), w("r"), w("t"), w("tab")
PPR, RPR, SECTPR = w("pPr"), w("rPr"), w("sectPr")
INS, DEL, MOVE_FROM, MOVE_TO = w("ins"), w("del"), w("moveFrom"), w("moveTo")
DEL_TEXT, INSTR, DEL_INSTR = w("delText"), w("instrText"), w("delInstrText")
FLD_CHAR, FLD_SIMPLE = w("fldChar"), w("fldSimple")
COMMENT_START, COMMENT_END = w("commentRangeStart"), w("commentRangeEnd")
COMMENT_REF = w("commentReference")

# Containers whose content is not the paragraph's running text.
NOT_TEXT = frozenset(
    {
        DEL,
        MOVE_FROM,
        PPR,
        RPR,
        SECTPR,
        w("sdtPr"),
        w("sdtEndPr"),
        w("customXmlPr"),
        w("smartTagPr"),
        w("drawing"),
        w("pict"),
        w("object"),
        w("txbxContent"),
        f"{{{MC}}}AlternateContent",
    }
)
# Markup that marks a point or range rather than content; kept when content around it goes.
RANGE_MARKS = frozenset(
    {
        COMMENT_START,
        COMMENT_END,
        w("bookmarkStart"),
        w("bookmarkEnd"),
        w("permStart"),
        w("permEnd"),
        w("proofErr"),
    }
)
# Blocks a paragraph range cannot step over.
BLOCKS = frozenset({P, w("tbl"), w("sdt"), w("customXml"), w("altChunk")})
