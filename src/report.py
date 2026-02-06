from __future__ import annotations
import os
import sys
import math
import json
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

import pandas as pd
from dateutil import parser as dateparser
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, BaseDocTemplate, PageTemplate, Frame
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY


CSV_COLUMNS = {
    "date_posted": "Data księgowania",
    "entry_type": "Typ zapisu",
    "doc_type": "Typ dokumentu",
    "doc_no": "Nr dokumentu",
    "item_no": "Nr zapasu",
    "search_desc": "Opis szukany",
    "source_no": "Nr źródła",
    "name": "Nazwa",
    "lot_no": "Nr partii",
    "expiry": "Data ważności",
    "location": "Kod lokalizacji",
    "qty": "Ilość",
}

# Possible alternative column names for Unit of Measure if present in CSV
UOM_ALIASES = [
    "Jednostka miary",
    "J.m.",
    "JM",
    "Jedn. miary",
    "Jednostka",
    "Jednostka sprzedaży",
    "Unit of Measure",
]


def _normalize_uom(s: Any) -> str:
    """Normalize unit strings to consistent uppercase short codes used in the PDF.
    Examples: KG, SZT, L, G, ML. Fallback to original trimmed uppercased value.
    """
    if s is None:
        return ""
    val = str(s).strip().upper()
    mapping = {
        "KG": "KG",
        "KILOGRAM": "KG",
        "KILOGRAMY": "KG",
        "SZT": "SZT",
        "SZTUKA": "SZT",
        "SZTUKI": "SZT",
        "L": "L",
        "LITR": "L",
        "LITRY": "L",
        "G": "G",
        "GRAM": "G",
        "GRAMY": "G",
        "ML": "ML",
        "MILILITR": "ML",
        "MILILITRY": "ML",
    }
    return mapping.get(val, val)


def _parse_date_any(s: Any) -> Optional[pd.Timestamp]:
    if pd.isna(s):
        return None
    if isinstance(s, pd.Timestamp):
        return s
    if isinstance(s, (int, float)) and not math.isnan(s):
        # Try Excel serial? Fallback to string
        s = str(s)
    try:
        # Many inputs like 11/21/2025, 3/1/2026, 26.02.2026, 2025-11-17, 20251221
        dt = dateparser.parse(str(s), dayfirst=False, yearfirst=False, fuzzy=True)
        return pd.Timestamp(dt.date()) if dt else None
    except Exception:
        try:
            dt = dateparser.parse(str(s), dayfirst=True, fuzzy=True)
            return pd.Timestamp(dt.date()) if dt else None
        except Exception:
            return None


def load_config(config_path: str) -> Dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_csv(csv_path: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(
            csv_path,
            encoding="utf-8-sig",
            dtype=str,  # read as str, we'll coerce specific fields
            keep_default_na=False,
        )
    except pd.errors.EmptyDataError:
        # File is empty or has no columns - return empty DataFrame
        return pd.DataFrame()
    
    # If DataFrame is empty (no rows), return it as-is
    if df.empty:
        return df

    # Normalize columns we need
    def get(col_key: str) -> str:
        return CSV_COLUMNS[col_key]

    # Coerce numeric quantity
    def to_float(v: str) -> float:
        if v is None:
            return 0.0
        s = str(v).strip().replace(" ", "")
        # handle non-breaking space used as thousand separator
        s = s.replace("\u00a0", "")
        
        # Remove quotes if present
        s = s.strip('"')
        
        try:
            return float(s)
        except Exception:
            # Detect if comma is thousand separator or decimal separator
            # If format is like "2,000" or "-2,000" (exactly 3 digits after comma), it's thousands
            # If format is like "2,5" or "2,50" (1-2 digits after comma), it's decimal
            if ',' in s:
                parts = s.replace('-', '').split(',')
                if len(parts) == 2 and len(parts[1]) == 3:
                    # Likely thousand separator: remove it
                    s = s.replace(',', '')
                else:
                    # Likely decimal separator: replace with dot
                    s = s.replace(',', '.')
            
            try:
                return float(s)
            except Exception:
                return 0.0

    df[get("qty")] = df[get("qty")].apply(to_float)

    # Parse dates into ISO strings for consistent output
    df[get("expiry")] = df[get("expiry")].apply(_parse_date_any)
    df[get("date_posted")] = df[get("date_posted")].apply(_parse_date_any)

    # Always defer unit resolution to external Jednostki.csv lookup (authoritative).
    # Ignore any in-file unit columns and heuristics; start with blank units.
    df["__UOM__"] = ""

    # Filter out rows where document number contains "/KG/" (case-sensitive)
    doc_col = get("doc_no")
    if doc_col in df.columns:
        mask = df[doc_col].astype(str).str.contains("/KG/", regex=False, na=False)
        df = df[~mask].copy()
    
    # Filter out rows where product name (Nazwa) starts with "OP-"
    name_col = get("name")
    if name_col in df.columns:
        mask = df[name_col].astype(str).str.startswith("OP-", na=False)
        df = df[~mask].copy()

    return df


def _extract_uom_from_name(name: Any) -> str:
    # Heuristic parse of units present in product name, e.g., "A'10 KG", "A'5L", "0,2KG" etc.
    import re
    s = str(name or "").upper()
    # Common tokens
    # Detect KG even when adjacent to digits without a leading space (e.g. 5KG, A'5KG, 0,2KG)
    if " KG" in s or "KG " in s or "KG" in s or re.search(r"[0-9]+\s*KG", s) or re.search(r"\bKG\b", s):
        return "KG"
    if re.search(r"\bL\b|\b L\b", s) or " 5L" in s:
        return "L"
    if " G " in s or re.search(r"\bG\b", s):
        return "G"
    if " ML" in s or re.search(r"\bML\b", s):
        return "ML"
    if " SZT" in s or re.search(r"\bSZT\b", s):
        return "SZT"
    # Fallback generic piece
    return "SZT"


def load_uom_lookup(lookup_csv_path: str) -> Dict[str, str]:
    """Load mapping of item number -> unit from a CSV/Excel like output/Jednostki.csv.
    Expects columns: 'Nr' and 'Podst. jednostka miary' (case-insensitive, partial match for 'jednostka').
    Returns dict {Nr: UOM}. If file is missing, tries a few fallback locations relative to the provided path.
    Gracefully returns {} if nothing is found/parsable.
    """
    def _try_read_csv(path: str) -> Optional[pd.DataFrame]:
        try:
            return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        except UnicodeDecodeError:
            try:
                return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="cp1250")
            except Exception:
                return None
        except Exception:
            return None

    def _try_read_excel(path: str) -> Optional[pd.DataFrame]:
        try:
            xl = pd.ExcelFile(path, engine="openpyxl")
            sheet = xl.sheet_names[0]
            return xl.parse(sheet).astype(str)
        except Exception:
            return None

    try:
        candidates: List[str] = []
        base = os.path.abspath(os.path.dirname(lookup_csv_path))
        # Executable directory (frozen) and potential repo root two levels up
        exec_dir = os.path.dirname(sys.executable)
        bundle_dir = getattr(sys, '_MEIPASS', None) or exec_dir
        repo_root_candidate = os.path.abspath(os.path.join(exec_dir, '..', '..'))
        # Primary: as provided
        candidates.append(lookup_csv_path)
        # Fallback: current working dir's output
        candidates.append(os.path.join(os.getcwd(), 'output', 'Jednostki.csv'))
        # Fallback: one and two levels up from base (useful when running dist/APApp and file is in project root/output)
        candidates.append(os.path.abspath(os.path.join(base, '..', 'Jednostki.csv')))
        candidates.append(os.path.abspath(os.path.join(base, '..', 'output', 'Jednostki.csv')))
        candidates.append(os.path.abspath(os.path.join(base, '..', '..', 'output', 'Jednostki.csv')))
        # Repo root output (common when running frozen exe from dist/APApp shortcut)
        candidates.append(os.path.join(repo_root_candidate, 'output', 'Jednostki.csv'))
        # Bundled inside PyInstaller (added via --add-data output/Jednostki.csv;output)
        candidates.append(os.path.join(bundle_dir, 'output', 'Jednostki.csv'))
        # Also allow 'data/Jednostki.csv' if present (Excel-misnamed)
        candidates.append(os.path.abspath(os.path.join(base, '..', 'data', 'Jednostki.csv')))
        candidates.append(os.path.abspath(os.path.join(base, '..', '..', 'data', 'Jednostki.csv')))
        candidates.append(os.path.join(repo_root_candidate, 'data', 'Jednostki.csv'))

        chosen: Optional[str] = next((p for p in candidates if p and os.path.exists(p)), None)
        if not chosen:
            return {}

        # Try CSV first, then Excel if needed
        df_l = _try_read_csv(chosen)
        if df_l is None:
            df_l = _try_read_excel(chosen)
        if df_l is None or df_l.empty:
            return {}

        # Find columns
        nr_col = None
        uom_col = None
        for c in df_l.columns:
            c_str = str(c).strip()
            if c_str.lower() in {"nr", "nr zapasu"}:
                nr_col = c
            if c_str.lower().startswith("podst.") or c_str.lower().startswith("podstawowa") or "jednostka" in c_str.lower():
                uom_col = c
        if nr_col is None or uom_col is None:
            return {}
        df_l = df_l[[nr_col, uom_col]].copy()
        df_l.columns = ["Nr", "UOM"]
        df_l["Nr"] = df_l["Nr"].astype(str).str.strip().str.upper()
        df_l["UOM"] = df_l["UOM"].map(_normalize_uom)
        mapping: Dict[str, str] = {}
        import re
        for _, r in df_l.iterrows():
            code = r["Nr"]
            uom = r["UOM"]
            if not code:
                continue
            mapping[code] = uom
            # If numeric-only (e.g. 3773) create padded variants: Z + zero + code until length 6 (Z0####)
            if re.fullmatch(r"\d{4,5}", code):
                digits = code
                # length 4 -> Z0 + digits (Z0####)
                if len(digits) == 4:
                    alt = f"Z0{digits}"  # Z0 + 4 digits => 6 chars
                    mapping.setdefault(alt, uom)
                # length 5 -> Z + digits (Z#####)
                if len(digits) == 5:
                    alt = f"Z{digits}"   # Z + 5 digits => 6 chars
                    mapping.setdefault(alt, uom)
            # If starts with Z and has 5 digits (Z#####) also add variant without leading zero (Z0####) if pattern matches
            if re.fullmatch(r"Z\d{5}", code):
                raw = code[1:]
                if raw.startswith('0') and len(raw) == 5:
                    # raw = 0#### => produce Z0#### already same code; also add digits-only without leading zero if 0####
                    mapping.setdefault(raw, uom)
                # If code like Z03773 add digits-only variant 3773
                if raw.startswith('0'):
                    digits4 = raw[1:]
                    if len(digits4) == 4:
                        mapping.setdefault(digits4, uom)
        return mapping
    except Exception:
        return {}


def apply_uom_lookup(df: pd.DataFrame, lookup: Dict[str, str]) -> pd.DataFrame:
    """Override df["__UOM__"] based on item number mapping when available.
    Does not modify other columns. Returns the same DataFrame (mutates in place).
    """
    try:
        item_col = CSV_COLUMNS["item_no"]
        if not lookup or item_col not in df.columns or "__UOM__" not in df.columns:
            return df
        mapped = df[item_col].astype(str).str.strip().str.upper().map(lookup)
        # Prefer mapped non-empty values; otherwise keep existing
        df["__UOM__"] = mapped.where(mapped.notna() & (mapped != ""), df["__UOM__"])
        return df
    except Exception:
        return df


def unique_sources(df: pd.DataFrame) -> List[str]:
    if df.empty:
        return []
    col = CSV_COLUMNS["source_no"]
    if col not in df.columns:
        return []
    vals = sorted({str(x).strip() for x in df[col].tolist() if str(x).strip()})
    return vals


def unique_search_names(df: pd.DataFrame) -> List[str]:
    """Return unique values from the 'Opis szukany' column."""
    col = CSV_COLUMNS["search_desc"]
    vals = sorted({str(x).strip() for x in df[col].tolist() if str(x).strip()})
    return vals


@dataclass
class ReportRow:
    lp: int
    name: str
    qty: float
    uom: str
    lot_no: str
    expiry: Optional[pd.Timestamp]
    item_no: str = ""  # Nr zapasu for special handling (e.g., z00155)


class ReportBuilder:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._ensure_fonts()

    def _ensure_fonts(self) -> None:
        """Register a Unicode font to render Polish diacritics.
        Preference order:
        - Fonts bundled in static/fonts (DejaVuSans.ttf / DejaVuSans-Bold.ttf)
        - Windows fonts (Arial / Segoe UI)
        Falls back to Helvetica if none found (may break diacritics).
        """
        base_dir = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        static_fonts = os.path.join(base_dir, "static", "fonts")

        candidates = [
            {
                "regular": os.path.join(static_fonts, "DejaVuSans.ttf"),
                "bold": os.path.join(static_fonts, "DejaVuSans-Bold.ttf"),
                "name": "DocFont",
            },
            {
                "regular": os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "arial.ttf"),
                "bold": os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "arialbd.ttf"),
                "name": "DocFont",
            },
            {
                "regular": os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "segoeui.ttf"),
                "bold": os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "segoeuib.ttf"),
                "name": "DocFont",
            },
        ]

        for c in candidates:
            try:
                if os.path.exists(c["regular"]) and os.path.exists(c["bold"]):
                    # Register under fixed names; skip if already registered
                    registered = set(pdfmetrics.getRegisteredFontNames())
                    if "DocFont" not in registered:
                        pdfmetrics.registerFont(TTFont("DocFont", c["regular"]))
                    if "DocFont-Bold" not in registered:
                        pdfmetrics.registerFont(TTFont("DocFont-Bold", c["bold"]))
                    try:
                        from reportlab.pdfbase.pdfmetrics import registerFontFamily
                        registerFontFamily('DocFont', normal='DocFont', bold='DocFont-Bold', italic='DocFont', boldItalic='DocFont-Bold')
                    except Exception:
                        pass
                    self.font_regular = "DocFont"
                    self.font_bold = "DocFont-Bold"
                    break
            except Exception:
                continue
        else:
            # Fallback to built-in Helvetica (may not render diacritics fully)
            self.font_regular = "Helvetica"
            self.font_bold = "Helvetica-Bold"

    def _get_styles(self):
        styles = getSampleStyleSheet()
        styles["Normal"].fontName = self.font_regular
        styles["Normal"].fontSize = 10
        styles["Normal"].leading = 13
        styles["Title"].fontName = self.font_bold
        styles["Title"].fontSize = 16
        styles["Title"].leading = 20
        # Custom lightweight styles
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
        styles.add(styles["Normal"].clone("HeaderSmall", fontName=self.font_regular, fontSize=10, leading=12, alignment=TA_LEFT))
        styles.add(styles["Normal"].clone("Cell", fontName=self.font_regular, fontSize=9, leading=11))
        styles.add(styles["Normal"].clone("CellCenter", fontName=self.font_regular, fontSize=9, leading=11, alignment=TA_CENTER))
        styles.add(styles["Normal"].clone("CellRight", fontName=self.font_regular, fontSize=9, leading=11, alignment=TA_RIGHT))
        styles.add(styles["Normal"].clone("Footer", fontName=self.font_regular, fontSize=9, leading=12, alignment=TA_JUSTIFY))
        return styles

    @staticmethod
    def _format_date_pl(ts: Optional[pd.Timestamp]) -> str:
        if isinstance(ts, pd.Timestamp):
            return ts.strftime("%d.%m.%Y")
        return ""

    @staticmethod
    def _format_qty_pl(q: float) -> str:
        # Use thin-space for thousands and comma decimal, trim trailing zeros
        try:
            n = float(q)
        except Exception:
            return ""
        if abs(n - round(n)) < 1e-9:
            s = f"{int(round(n)):,}"
        else:
            s = f"{n:,.3f}"
            s = s.rstrip('0').rstrip('.')
        s = s.replace(",", "_").replace(".", ",").replace("_", "\u202f")
        return s

    def build_rows_for_document(self, df: pd.DataFrame) -> List[ReportRow]:
        name_col = CSV_COLUMNS["name"]
        lot_col = CSV_COLUMNS["lot_no"]
        exp_col = CSV_COLUMNS["expiry"]
        qty_col = CSV_COLUMNS["qty"]
        doc_type_col = CSV_COLUMNS["doc_type"]
        item_col = CSV_COLUMNS["item_no"]

        # Consider only rows of a single document (df already filtered by doc outside)
        # Prefer explicit document type if present to limit to outbound (Wydanie sprzedaży)
        df_use = df.copy()
        if doc_type_col in df_use.columns:
            mask = (df_use[doc_type_col].str.contains("Wydanie sprzedaży", na=False)) | (df_use[qty_col] < 0)
            df_use = df_use[mask]

        # Group by Name + Lot + Expiry + Item_no (+ UOM) and sum absolute quantities within the document
        group_cols = [name_col, lot_col, exp_col, item_col, "__UOM__"]
        grouped = (
            df_use.groupby(group_cols, dropna=False)[qty_col]
            .sum()
            .reset_index()
        )

        # Stable sorting by Name -> Lot -> Expiry
        grouped = grouped.sort_values(by=[name_col, lot_col, exp_col], kind="stable")

        rows: List[ReportRow] = []
        lp = 1
        for _, r in grouped.iterrows():
            name = str(r.get(name_col, "")).strip()
            lot = str(r.get(lot_col, "")).strip()
            exp = r.get(exp_col)
            qty = r.get(qty_col, 0.0)
            qty_pos = abs(float(qty))
            uom = str(r.get("__UOM__", "")).strip()
            item_no = str(r.get(item_col, "")).strip()
            rows.append(ReportRow(lp=lp, name=name, qty=qty_pos, uom=uom, lot_no=lot, expiry=exp, item_no=item_no))
            lp += 1
        return rows

    def infer_doc_header(self, df: pd.DataFrame) -> Tuple[str, str]:
        doc_no_col = CSV_COLUMNS["doc_no"]
        date_col = CSV_COLUMNS["date_posted"]
        doc_no = None
        date_str = None
        if doc_no_col in df.columns:
            doc_no = next((str(v).strip() for v in df[doc_no_col].tolist() if str(v).strip()), "")
        if date_col in df.columns:
            dt = next((v for v in df[date_col].tolist() if isinstance(v, pd.Timestamp)), None)
            if dt is None:
                # Try string to parse
                raw = next((str(v).strip() for v in df[date_col].tolist() if str(v).strip()), "")
                dt = _parse_date_any(raw)
            if isinstance(dt, pd.Timestamp):
                date_str = dt.strftime("%d.%m.%Y")
        return doc_no or "", date_str or ""

    def generate_pdf(self, output_path: str, rows: List[ReportRow], header: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        # Margins (keep current defaults; configurable via config.json -> margins_mm)
        mcfg = self.config.get("margins_mm", {"left": 15, "right": 15, "top": 15, "bottom": 18})
        left_m = float(mcfg.get("left", 15)) * mm
        right_m = float(mcfg.get("right", 15)) * mm
        top_m = float(mcfg.get("top", 15)) * mm
        bottom_m = float(mcfg.get("bottom", 18)) * mm
        
        # Create document
        doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=left_m, rightMargin=right_m, topMargin=top_m, bottomMargin=bottom_m)
        
        styles = self._get_styles()

        story = []
        # Optional logo at the very top (from config.logo_path or <app>/logo.png)
        data_root = (os.path.dirname(sys.executable) if getattr(sys, "_MEIPASS", None) else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        bundle_root = getattr(sys, "_MEIPASS", None) or data_root
        configured = str(self.config.get("logo_path", "")).strip()
        candidates = [
            configured if configured else None,
            os.path.join(data_root, "logo.png"),    # external beside EXE or in repo root
            os.path.join(bundle_root, "logo.png"),  # bundled via PyInstaller datas
        ]
        logo_path = next((p for p in candidates if p and os.path.exists(p)), None)
        if logo_path and os.path.exists(logo_path):
            try:
                img = Image(logo_path)
                # Fit within a reasonable header box
                max_w = 60 * mm
                max_h = 24 * mm
                img._restrictSize(max_w, max_h)
                story.append(img)
                story.append(Spacer(1, 6))
            except Exception:
                pass
        # Header addresses
        for line in self.config.get("company_header", []):
            story.append(Paragraph(line, styles["HeaderSmall"]))
        story.append(Spacer(1, 6))

        # Title
        title = self.config.get("title", "Raport")
        story.append(Paragraph(f"<b>{title}</b>", styles["Title"]))

        # Customer name (if provided)
        customer_name = header.get("customer_name", "")
        if customer_name:
            story.append(Paragraph(f"dla {customer_name}", styles["Normal"]))
        
        # Document info lines
        doc_no = header.get("document_no", "")
        doc_date = header.get("document_date", "")
        if doc_no:
            story.append(Paragraph(f"do dokumentu {doc_no}", styles["Normal"]))
        if doc_date:
            story.append(Paragraph(f"z dnia {doc_date}", styles["Normal"]))
        story.append(Spacer(1, 10))

        # Table header and data (with Unit column and readable layout)
        data = [[
            Paragraph("Lp.", styles["CellCenter"]),
            Paragraph("NAZWA PRODUKTU", styles["CellCenter"]),
            Paragraph("ILOŚĆ", styles["CellCenter"]),
            Paragraph("JEDN. MIARY", styles["CellCenter"]),
            Paragraph("NR PARTII LOT", styles["CellCenter"]),
            Paragraph("DATA MINIMALNEJ TRWAŁOŚCI LUB TERMIN PRZYDATNOŚCI DO SPOŻYCIA", styles["CellCenter"]),
        ]]
        # Add rows
        for r in rows:
            # Special handling for z00155: always show "nie dotyczy" in italic
            if r.item_no.lower() == "z00155":
                exp_str = "<i>nie dotyczy</i>"
            else:
                exp_str = self._format_date_pl(r.expiry)
            qty_str = self._format_qty_pl(r.qty)
            data.append([
                Paragraph(str(r.lp), styles["CellCenter"]),
                Paragraph(r.name, styles["Cell"]),
                Paragraph(qty_str, styles["CellRight"]),
                Paragraph(r.uom, styles["CellCenter"]),
                Paragraph(r.lot_no, styles["CellCenter"]),
                Paragraph(exp_str, styles["CellCenter"]),
            ])

        # Scale column widths to available page width (A4 width minus margins)
        page_width_pt = A4[0]
        avail_width_pt = page_width_pt - left_m - right_m
        weights = [12, 78, 20, 22, 36, 42]
        total_w = float(sum(weights)) or 1.0
        col_widths = [avail_width_pt * (w / total_w) for w in weights]
        tbl = Table(data, repeatRows=1, colWidths=col_widths)
        tbl.setStyle(TableStyle([
            ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
            ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
            ("ALIGN", (0,0), (-1,0), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING", (0,0), (-1,-1), 5),
            ("RIGHTPADDING", (0,0), (-1,-1), 5),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("ALIGN", (2,1), (2,-1), "RIGHT"),  # quantity right aligned
            ("FONT", (0,0), (-1,-1), self.font_regular, 10),
            ("FONT", (0,0), (-1,0), self.font_bold, 10),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 14))

        # Footers
        for ft in self.config.get("footer_texts", []):
            story.append(Paragraph(ft, styles["Footer"]))
            story.append(Spacer(1, 6))

        # Build PDF with page numbers using custom canvas
        from reportlab.pdfgen import canvas as pdfgen_canvas
        
        class NumberedCanvas(pdfgen_canvas.Canvas):
            def __init__(self, *args, **kwargs):
                pdfgen_canvas.Canvas.__init__(self, *args, **kwargs)
                self._saved_page_states = []
                
            def showPage(self):
                self._saved_page_states.append(dict(self.__dict__))
                self._startPage()
                
            def save(self):
                """Add page numbers to all pages"""
                num_pages = len(self._saved_page_states)
                for state in self._saved_page_states:
                    self.__dict__.update(state)
                    self.draw_page_number(num_pages)
                    pdfgen_canvas.Canvas.showPage(self)
                pdfgen_canvas.Canvas.save(self)
                
            def draw_page_number(self, page_count):
                page_num = self._pageNumber
                if page_count > 1:
                    text = f"Strona {page_num}/{page_count}"
                else:
                    text = f"Strona {page_num}"
                self.saveState()
                self.setFont(font_regular, 9)
                self.drawRightString(A4[0] - right_m, bottom_m - 10, text)
                self.restoreState()
        
        # Need to pass font to canvas
        font_regular = self.font_regular
        
        doc.build(story, canvasmaker=NumberedCanvas)


def filter_by_sources(df: pd.DataFrame, sources: List[str]) -> pd.DataFrame:
    col = CSV_COLUMNS["source_no"]
    return df[df[col].isin(sources)].copy()


def filter_by_search_names(df: pd.DataFrame, names: List[str]) -> pd.DataFrame:
    col = CSV_COLUMNS["search_desc"]
    return df[df[col].isin(names)].copy()
