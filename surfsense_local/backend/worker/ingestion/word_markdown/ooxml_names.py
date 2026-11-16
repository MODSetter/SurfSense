"""The WordprocessingML element and attribute names the reader matches, in Clark form."""

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"


def w(local: str) -> str:
    return f"{{{W_NS}}}{local}"


VAL = w("val")
R_ID = f"{{{R_NS}}}id"

BODY = w("body")
P = w("p")
R = w("r")
T = w("t")
TBL = w("tbl")
TR = w("tr")
TC = w("tc")
SDT = w("sdt")
SDT_CONTENT = w("sdtContent")
CUSTOM_XML = w("customXml")
HYPERLINK = w("hyperlink")
TXBX_CONTENT = w("txbxContent")
P_PR = w("pPr")
P_STYLE = w("pStyle")
NUM_PR = w("numPr")
NUM_ID = w("numId")
ILVL = w("ilvl")
OUTLINE_LVL = w("outlineLvl")

M_T = f"{{{M_NS}}}t"
M_OMATH = f"{{{M_NS}}}oMath"
M_OMATH_PARA = f"{{{M_NS}}}oMathPara"
A_T = f"{{{A_NS}}}t"
MC_ALTERNATE_CONTENT = f"{{{MC_NS}}}AlternateContent"
MC_CHOICE = f"{{{MC_NS}}}Choice"
MC_FALLBACK = f"{{{MC_NS}}}Fallback"
