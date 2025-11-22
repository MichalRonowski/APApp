from __future__ import annotations
import os
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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


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
    df = pd.read_csv(
        csv_path,
        encoding="utf-8-sig",
        dtype=str,  # read as str, we'll coerce specific fields
        keep_default_na=False,
    )

    # Normalize columns we need
    def get(col_key: str) -> str:
        return CSV_COLUMNS[col_key]

    # Coerce numeric quantity
    def to_float(v: str) -> float:
        if v is None:
            return 0.0
        s = str(v).strip().replace(" ", "")
        # handle comma thousand separator in currency columns if leaked
        s = s.replace("\u00a0", "")
        try:
            return float(s)
        except Exception:
            # Try comma decimal
            try:
                return float(s.replace(",", "."))
            except Exception:
                return 0.0

    df[get("qty")] = df[get("qty")].apply(to_float)

    # Parse dates into ISO strings for consistent output
    df[get("expiry")] = df[get("expiry")].apply(_parse_date_any)
    df[get("date_posted")] = df[get("date_posted")].apply(_parse_date_any)

    # Try to find Unit of Measure column
    uom_col = None
    for alias in UOM_ALIASES:
        if alias in df.columns:
            uom_col = alias
            break
    if uom_col is None:
        # Create placeholder to be filled via extraction from name
        df["__UOM__"] = df[CSV_COLUMNS["name"]].apply(_extract_uom_from_name)
    else:
        df["__UOM__"] = df[uom_col].astype(str)

    return df


def _extract_uom_from_name(name: Any) -> str:
    # Heuristic parse of units present in product name, e.g., "A'10 KG", "A'5L", "0,2KG" etc.
    import re
    s = str(name or "").upper()
    # Common tokens
    if " KG" in s or re.search(r"\bKG\b", s):
        return "kg"
    if re.search(r"\bL\b|\b L\b", s) or " 5L" in s:
        return "l"
    if " G " in s or re.search(r"\bG\b", s):
        return "g"
    if " ML" in s or re.search(r"\bML\b", s):
        return "ml"
    if " SZT" in s or re.search(r"\bSZT\b", s):
        return "szt"
    # Fallback generic piece
    return "szt"


def unique_sources(df: pd.DataFrame) -> List[str]:
    col = CSV_COLUMNS["source_no"]
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
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

        # Consider only rows of a single document (df already filtered by doc outside)
        # Prefer explicit document type if present to limit to outbound (Wydanie sprzedaży)
        df_use = df.copy()
        if doc_type_col in df_use.columns:
            mask = (df_use[doc_type_col].str.contains("Wydanie sprzedaży", na=False)) | (df_use[qty_col] < 0)
            df_use = df_use[mask]

        # Group by Name + Lot + Expiry (+ UOM) and sum absolute quantities within the document
        group_cols = [name_col, lot_col, exp_col, "__UOM__"]
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
            rows.append(ReportRow(lp=lp, name=name, qty=qty_pos, uom=uom, lot_no=lot, expiry=exp))
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
        doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=left_m, rightMargin=right_m, topMargin=top_m, bottomMargin=bottom_m)
        styles = self._get_styles()

        story = []
        # Header addresses
        for line in self.config.get("company_header", []):
            story.append(Paragraph(line, styles["HeaderSmall"]))
        story.append(Spacer(1, 6))

        # Title
        title = self.config.get("title", "Raport")
        story.append(Paragraph(f"<b>{title}</b>", styles["Title"]))

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

        col_widths = [12*mm, 78*mm, 20*mm, 22*mm, 36*mm, 42*mm]
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

        doc.build(story)


def filter_by_sources(df: pd.DataFrame, sources: List[str]) -> pd.DataFrame:
    col = CSV_COLUMNS["source_no"]
    return df[df[col].isin(sources)].copy()
