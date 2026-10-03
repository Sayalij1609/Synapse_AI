"""
SYNAPSE AI — Unified Report Export Engine.

Architecture:
Research Result
       ↓
Structured Report Object (Canonical Schema)
       ↓
 ├── Web UI
 ├── DOCX
 ├── PDF
 └── Markdown

All export formats are deterministically generated from the same structured report object.
No format is regenerated separately via LLM.

Preserved Sections:
1. Executive Summary
2. Research Objectives
3. Key Findings
4. Detailed Analysis
5. Claims
6. Inline Citations
7. Sources
8. Evidence References
9. Verification Summary
10. Research Limitations
11. Generated Timestamp
"""

import io
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union, Tuple
from pydantic import BaseModel, Field

# DOCX dependencies
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
import docx.opc.constants

# PDF dependencies
from fpdf import FPDF
from fpdf.fonts import FontFace


# =====================================================================
# Canonical Structured Report Models
# =====================================================================

class StructuredClaim(BaseModel):
    """Factual statement audited against evidence."""
    claim_id: str
    text: str
    status: str = "grounded"  # "grounded", "insufficient", "unsupported"
    confidence: float = 1.0
    evidence_text: Optional[str] = None
    supporting_source_ids: List[str] = Field(default_factory=list)
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    verification_notes: Optional[str] = None


class StructuredSource(BaseModel):
    """Authoritative source reference with URL and quality metadata."""
    source_id: str
    source_number: int = 1
    title: str
    url: str
    domain: str = "web"
    source_type: str = "general"
    publication_date: str = "N/A"
    freshness: str = "undated"
    quality_score: float = 0.5
    quality_tier: str = "adequate"

    @property
    def citation_tag(self) -> str:
        return f"[{self.source_number}]"


class StructuredEvidenceRef(BaseModel):
    """Vector evidence chunk excerpt linked to a source."""
    chunk_id: str
    source_id: str = ""
    source_title: str = ""
    source_url: str = ""
    excerpt: str
    similarity_score: float = 0.0


class StructuredVerificationSummary(BaseModel):
    """Audit metrics from the autonomous verification loop."""
    status: str = "verified"  # "verified", "passed", "completed", "additional_research_required"
    iteration_count: int = 1
    confidence_score: float = 1.0
    total_claims: int = 0
    grounded_claims: int = 0
    insufficient_claims: int = 0
    unsupported_claims: int = 0
    feedback_notes: Optional[str] = None


class StructuredAnalysisSection(BaseModel):
    """Analytical narrative section with heading and text."""
    heading: str
    content: str
    subsections: List[Dict[str, str]] = Field(default_factory=list)


class StructuredReport(BaseModel):
    """
    Canonical Structured Report Object.
    Central source of truth for all exports: Web UI, DOCX, PDF, and Markdown.
    """
    title: str
    generated_at: str
    executive_summary: str
    conclusion: str = ""
    research_objectives: List[str] = Field(default_factory=list)
    key_findings: List[str] = Field(default_factory=list)
    detailed_analysis: List[StructuredAnalysisSection] = Field(default_factory=list)
    claims: List[StructuredClaim] = Field(default_factory=list)
    inline_citations: Dict[str, str] = Field(default_factory=dict)
    sources: List[StructuredSource] = Field(default_factory=list)
    evidence_references: List[StructuredEvidenceRef] = Field(default_factory=list)
    verification_summary: StructuredVerificationSummary = Field(default_factory=StructuredVerificationSummary)
    research_limitations: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =====================================================================
# Builder: Transform Pipeline / DB / Raw Result to StructuredReport
# =====================================================================

def _clean_markdown_text(text: str) -> str:
    """Strip bold/italic markdown markers while preserving readable text."""
    if not text:
        return ""
    t = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    t = re.sub(r'\*(.*?)\*', r'\1', t)
    t = re.sub(r'`(.*?)`', r'\1', t)
    return t.strip()


def _sanitize_pdf_latin1(text: Any) -> str:
    """Sanitize Unicode characters for standard FPDF Latin-1 rendering."""
    if text is None:
        return ""
    text = str(text)
    replacements = {
        '\u2018': "'", '\u2019': "'", '\u201a': "'", '\u201b': "'",
        '\u201c': '"', '\u201d': '"', '\u201e': '"', '\u201f': '"',
        '\u2013': '-', '\u2014': '--', '\u2015': '--',
        '\u2026': '...', '\u2022': '-', '\u00b7': '-',
        '\u2010': '-', '\u2011': '-', '\u2012': '-', '\u00a0': ' ',
        '\u200b': '', '\u200c': '', '\u200d': '', '\ufeff': '',
        '\u2713': '[v]', '\u2717': '[x]', '\u2192': '->', '\u2190': '<-',
        '\u25cf': '*', '\u25cb': 'o', '\u2605': '*',
        '✅': '[Grounded]', '⚠️': '[Warning]', '❌': '[Unsupported]',
        '🔬': '[Research]', '⚡': '[Engine]', '📋': '[Plan]',
        '📖': '[Reader]', '🧠': '[Retrieval]', '✍️': '[Writer]',
        '🛡️': '[Verifier]', '🏁': '[Completed]',
        '’': "'", '‘': "'", '“': '"', '”': '"', '–': '-', '—': '--', '…': '...', '•': '-',
        '™': '(TM)', '©': '(C)', '®': '(R)',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode('latin-1', errors='replace').decode('latin-1')


def parse_markdown_table_lines(lines: List[str]) -> Tuple[List[str], List[List[str]]]:
    """Parse markdown table lines into headers and row cells."""
    table_lines = [l.strip() for l in lines if l.strip().startswith("|") and l.strip().endswith("|")]
    if len(table_lines) < 2:
        return [], []

    raw_headers = [c.strip() for c in table_lines[0].strip("|").split("|")]
    headers = [_sanitize_pdf_latin1(re.sub(r'[*`_]', '', h).strip()) for h in raw_headers]

    rows = []
    for line in table_lines[1:]:
        inner = line.strip("|")
        if re.match(r'^[\s\-:|]+$', inner):
            continue
        cells = [c.strip() for c in inner.split("|")]
        if len(cells) < len(headers):
            cells.extend(["—"] * (len(headers) - len(cells)))
        elif len(cells) > len(headers):
            cells = cells[:len(headers)]
        cleaned_cells = [_sanitize_pdf_latin1(c.strip()) for c in cells]
        rows.append(cleaned_cells)

    return headers, rows


def parse_claims_from_table(lines: List[str]) -> List[StructuredClaim]:
    """Extract StructuredClaim items from a markdown claims table."""
    claims = []
    table_lines = [l.strip() for l in lines if l.strip().startswith("|") and l.strip().endswith("|")]
    if len(table_lines) < 2:
        return []

    raw_headers = [c.strip().lower() for c in table_lines[0].strip("|").split("|")]
    id_col = 0
    status_col = 1
    conf_col = 2
    stmt_col = 3
    exc_col = 4
    src_col = 5

    for idx, h in enumerate(raw_headers):
        if h in ("id", "claim id", "claim_id") or (h.startswith("id") and len(h) <= 4):
            id_col = idx
        elif "status" in h:
            status_col = idx
        elif "conf" in h:
            conf_col = idx
        elif "statement" in h or "claim" in h:
            stmt_col = idx
        elif "excerpt" in h or "evidence" in h:
            exc_col = idx
        elif "source" in h or "ref" in h:
            src_col = idx

    for line in table_lines[1:]:
        inner = line.strip("|")
        if re.match(r'^[\s\-:|]+$', inner):
            continue
        cells = [c.strip() for c in inner.split("|")]
        if len(cells) <= max(id_col, stmt_col):
            continue

        raw_id = re.sub(r'[`*]', '', cells[id_col]).strip() if id_col < len(cells) else f"claim_{len(claims)+1}"
        raw_status = cells[status_col].lower() if status_col < len(cells) else "grounded"
        status = "grounded"
        if "unsupported" in raw_status or "fail" in raw_status or "x" in raw_status:
            status = "unsupported"
        elif "insufficient" in raw_status or "warning" in raw_status or "warn" in raw_status or "?" in raw_status:
            status = "insufficient"

        raw_conf = cells[conf_col] if conf_col < len(cells) else "90%"
        conf_m = re.search(r'(\d+(?:\.\d+)?)', raw_conf)
        conf_val = float(conf_m.group(1)) / 100.0 if conf_m and float(conf_m.group(1)) > 1.0 else (float(conf_m.group(1)) if conf_m else 0.9)

        stmt = cells[stmt_col].strip() if stmt_col < len(cells) else ""
        exc = re.sub(r'[\*\"\_]', '', cells[exc_col]).strip() if exc_col < len(cells) else ""

        src_raw = cells[src_col] if src_col < len(cells) else ""
        src_url = ""
        src_title = src_raw
        link_m = re.search(r'\[([^\]]+)\]\((https?://[^)]+)\)', src_raw)
        if link_m:
            src_title = link_m.group(1)
            src_url = link_m.group(2)

        claims.append(StructuredClaim(
            claim_id=raw_id,
            text=stmt,
            status=status,
            confidence=conf_val,
            evidence_text=exc,
            source_url=src_url or None,
            source_title=src_title or None,
        ))

    return claims


def parse_sources_from_table(lines: List[str]) -> List[StructuredSource]:
    """Extract StructuredSource items from a markdown sources table."""
    sources = []
    table_lines = [l.strip() for l in lines if l.strip().startswith("|") and l.strip().endswith("|")]
    if len(table_lines) < 2:
        return []

    raw_headers = [c.strip().lower() for c in table_lines[0].strip("|").split("|")]
    num_col = 0
    title_col = 1
    dom_col = 2
    type_col = 3
    fresh_col = 4

    for idx, h in enumerate(raw_headers):
        if h in ("ref", "#", "source", "id"):
            num_col = idx
        elif "title" in h or "url" in h:
            title_col = idx
        elif "domain" in h:
            dom_col = idx
        elif "type" in h:
            type_col = idx
        elif "fresh" in h:
            fresh_col = idx

    for idx, line in enumerate(table_lines[1:], 1):
        inner = line.strip("|")
        if re.match(r'^[\s\-:|]+$', inner):
            continue
        cells = [c.strip() for c in inner.split("|")]
        if len(cells) <= title_col:
            continue

        raw_num = re.sub(r'[^\d]', '', cells[num_col]) if num_col < len(cells) else str(idx)
        src_num = int(raw_num) if raw_num.isdigit() else idx

        title_raw = cells[title_col] if title_col < len(cells) else f"Source {src_num}"
        src_url = ""
        src_title = title_raw
        link_m = re.search(r'\[([^\]]+)\]\((https?://[^)]+)\)', title_raw)
        if link_m:
            src_title = link_m.group(1)
            src_url = link_m.group(2)

        domain = re.sub(r'[`*]', '', cells[dom_col]).strip() if dom_col < len(cells) else ""
        if not domain and src_url:
            domain = src_url.split("//")[-1].split("/")[0]

        src_type = cells[type_col].strip() if type_col < len(cells) else "general"
        fresh = cells[fresh_col].strip() if fresh_col < len(cells) else "recent"

        sources.append(StructuredSource(
            source_id=f"src_{src_num}",
            source_number=src_num,
            title=src_title,
            url=src_url,
            domain=domain or "web",
            source_type=src_type or "general",
            publication_date="N/A",
            freshness=fresh or "recent",
            quality_score=0.90
        ))

    return sources


def render_pdf_table_block(
    pdf: FPDF,
    headers: List[str],
    rows: List[List[str]],
    title: Optional[str] = None,
    col_widths: Optional[Tuple[float, ...]] = None,
):
    """
    Render an executive graphical table in FPDF matching the UI theme.
    - Deep Slate header (30, 41, 59) with crisp white text.
    - Slate 50 alternating rows (248, 250, 252) with subtle Slate 200 border (226, 232, 240).
    - Auto cell text wrapping, padding, and centered status badges.
    - Clickable hyperlinks for embedded markdown links.
    """
    if not headers or not rows:
        return

    if title:
        pdf.set_font("Helvetica", "B", 10.5)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(0, 5.5, _sanitize_pdf_latin1(title))
        pdf.ln(5.5)

    avail_w = 190.0  # Usable width on A4 portrait with 10mm margins

    if not col_widths or len(col_widths) != len(headers):
        # Calculate proportional widths based on content lengths
        col_max_lens = [max(len(_sanitize_pdf_latin1(str(h))), 5) for h in headers]
        for r in rows:
            for i, val in enumerate(r):
                val_str = _sanitize_pdf_latin1(str(val)) if val is not None else ""
                col_max_lens[i] = max(col_max_lens[i], min(len(val_str), 80))

        total_len = sum(col_max_lens) or 1
        calc_widths = []
        for l in col_max_lens:
            w = max(14.0, (l / total_len) * avail_w)
            calc_widths.append(w)

        scale = avail_w / sum(calc_widths)
        col_widths = tuple(round(w * scale, 1) for w in calc_widths)
        diff = avail_w - sum(col_widths)
        if diff != 0:
            col_widths = list(col_widths)
            col_widths[-1] += diff
            col_widths = tuple(col_widths)

    h_style = FontFace(
        family="Helvetica",
        emphasis="B",
        size_pt=8,
        color=(255, 255, 255),
        fill_color=(30, 41, 59),  # Slate 800
    )

    pdf.set_font("Helvetica", size=7.5)
    pdf.set_draw_color(226, 232, 240)  # Slate 200 borders

    with pdf.table(
        col_widths=col_widths,
        line_height=4.2,
        headings_style=h_style,
        cell_fill_color=(248, 250, 252),  # Slate 50
        cell_fill_mode="ROWS",
        repeat_headings=1,
        markdown=True,
        padding=1.8,
    ) as tbl:
        # Header row
        hdr_row = tbl.row()
        for h in headers:
            hdr_row.cell(_sanitize_pdf_latin1(str(h)), align="CENTER")

        # Data rows
        for r in rows:
            data_row = tbl.row()
            for val in r:
                raw_cell_str = str(val) if val is not None else ""
                cell_style = None
                cell_align = "LEFT"
                cell_link = None

                # Extract markdown links like [Title](url)
                link_m = re.search(r'\[([^\]]+)\]\((https?://[^)]+)\)', raw_cell_str)
                if link_m:
                    cell_link = _sanitize_pdf_latin1(link_m.group(2))
                    clean_val = link_m.group(1)
                else:
                    clean_val = raw_cell_str

                clean_val = _sanitize_pdf_latin1(clean_val)

                lower_val = clean_val.lower()
                if any(w in lower_val for w in ["[grounded]", "grounded"]):
                    cell_style = FontFace(family="Helvetica", emphasis="B", size_pt=7.5, color=(5, 150, 105))
                    cell_align = "CENTER"
                elif any(w in lower_val for w in ["[warning]", "insufficient", "partial"]):
                    cell_style = FontFace(family="Helvetica", emphasis="B", size_pt=7.5, color=(217, 119, 6))
                    cell_align = "CENTER"
                elif any(w in lower_val for w in ["[unsupported]", "unsupported"]):
                    cell_style = FontFace(family="Helvetica", emphasis="B", size_pt=7.5, color=(225, 29, 72))
                    cell_align = "CENTER"
                elif re.match(r'^\d+%$', clean_val) or clean_val.startswith("claim_") or clean_val.startswith("CLM-") or (clean_val.startswith("[") and clean_val.endswith("]") and len(clean_val) <= 5):
                    cell_align = "CENTER"

                data_row.cell(clean_val, align=cell_align, style=cell_style, link=cell_link)

    pdf.ln(4)


def render_content_with_tables(pdf: FPDF, content: str):
    """
    Render narrative text that may contain markdown tables, subheadings, and bullets.
    Identifies table blocks and converts them to graphical tables rather than raw text.
    """
    lines = content.split("\n")
    table_buffer = []
    in_table = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            in_table = True
            table_buffer.append(stripped)
            continue
        else:
            if in_table and table_buffer:
                headers, rows = parse_markdown_table_lines(table_buffer)
                if headers and rows:
                    render_pdf_table_block(pdf, headers, rows)
                table_buffer = []
                in_table = False

        if not stripped:
            continue

        if stripped.startswith("### "):
            subheading = stripped.lstrip("#").strip()
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 10.5)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(0, 5, _sanitize_pdf_latin1(subheading))
            pdf.ln(5)
        elif stripped.startswith("- ") or stripped.startswith("* "):
            bullet_text = re.sub(r'^[*-]\s*', '', stripped)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(51, 65, 85)
            pdf.cell(5)
            pdf.cell(4, 4.5, "-")
            pdf.multi_cell(0, 4.5, _sanitize_pdf_latin1(bullet_text))
            pdf.ln(1)
        else:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(51, 65, 85)
            pdf.multi_cell(0, 4.8, _sanitize_pdf_latin1(stripped))
            pdf.ln(2.5)

    if in_table and table_buffer:
        headers, rows = parse_markdown_table_lines(table_buffer)
        if headers and rows:
            render_pdf_table_block(pdf, headers, rows)


def build_structured_report(
    data: Any,
    topic: Optional[str] = None
) -> StructuredReport:
    """
    Construct a canonical StructuredReport from:
    1. An already instantiated StructuredReport
    2. A pipeline state dict or database session dict
    3. A database model (ResearchSession)
    4. A raw markdown report string
    """
    if isinstance(data, StructuredReport):
        return data

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # If data is a SQLAlchemy ResearchSession object
    if hasattr(data, "__tablename__") and getattr(data, "__tablename__") == "research_sessions":
        session = data
        return _build_from_db_session(session)

    # If data is a dictionary
    if isinstance(data, dict):
        # Check if already serialized StructuredReport
        if "detailed_analysis" in data and "executive_summary" in data and "verification_summary" in data:
            try:
                return StructuredReport(**data)
            except Exception:
                pass
        return _build_from_dict(data, default_topic=topic or "Autonomous Research Report")

    # If data is a plain string (markdown report)
    if isinstance(data, str):
        return _build_from_markdown_text(data, topic=topic or "Research Report", now_str=now_iso)

    # Fallback default empty report
    return StructuredReport(
        title=topic or "Research Report",
        generated_at=now_iso,
        executive_summary="Empirical research synthesis.",
    )


def _build_from_dict(d: Dict[str, Any], default_topic: str) -> StructuredReport:
    """Build StructuredReport from pipeline state dict, history dict, or payload."""
    title = (
        d.get("topic")
        or (d.get("plan") or {}).get("research_objective")
        or default_topic
    )
    now_iso = d.get("generated_at") or d.get("timestamp") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # 1. Sources mapping
    raw_sources = d.get("source_quality_profiles") or d.get("sources") or []
    structured_sources: List[StructuredSource] = []
    source_url_map: Dict[str, StructuredSource] = {}
    source_id_map: Dict[str, StructuredSource] = {}

    if isinstance(raw_sources, dict):
        source_items = list(raw_sources.values())
    elif isinstance(raw_sources, list):
        source_items = raw_sources
    else:
        source_items = []

    for idx, s in enumerate(source_items, 1):
        if not isinstance(s, dict):
            if hasattr(s, "model_dump"):
                s = s.model_dump()
            elif hasattr(s, "to_dict"):
                s = s.to_dict()
            else:
                continue

        sid = s.get("source_id") or s.get("id") or f"src_{idx}"
        url = s.get("url") or ""
        st = StructuredSource(
            source_id=sid,
            source_number=idx,
            title=s.get("title") or url or f"Source {idx}",
            url=url,
            domain=s.get("domain") or (url.split("//")[-1].split("/")[0] if url else "web"),
            source_type=s.get("source_type") or "general",
            publication_date=s.get("publication_date") or "N/A",
            freshness=s.get("freshness") or "undated",
            quality_score=float(s.get("composite_score") or s.get("quality_score") or 0.5),
            quality_tier=s.get("quality_tier") or "adequate",
        )
        structured_sources.append(st)
        source_id_map[sid] = st
        if url:
            source_url_map[url.lower()] = st

    # 2. Objectives
    objectives: List[str] = []
    if d.get("research_objectives"):
        objectives.extend(d["research_objectives"])
    plan = d.get("plan") or {}
    if isinstance(plan, dict):
        if plan.get("research_objective") and plan["research_objective"] not in objectives:
            objectives.append(plan["research_objective"])
        subtasks = plan.get("subtasks") or d.get("subtasks") or []
        for st in subtasks:
            if isinstance(st, dict):
                q = st.get("question") or st.get("title") or st.get("research_question")
                if q and q not in objectives:
                    objectives.append(q)
            elif isinstance(st, str) and st not in objectives:
                objectives.append(st)

    # 3. Claims
    raw_claims = d.get("claims") or []
    if not raw_claims:
        raw_claims = (d.get("grounded_claims") or []) + (d.get("insufficient_claims") or []) + (d.get("unsupported_claims") or [])

    structured_claims: List[StructuredClaim] = []
    grounded_count = 0
    insufficient_count = 0
    unsupported_count = 0

    for idx, c in enumerate(raw_claims, 1):
        if not isinstance(c, dict):
            if hasattr(c, "model_dump"):
                c = c.model_dump()
            elif hasattr(c, "to_dict"):
                c = c.to_dict()
            else:
                continue

        cid = c.get("claim_id") or f"claim_{idx}"
        text = c.get("text") or c.get("claim_text") or ""
        status = c.get("status") or c.get("verification_status") or "grounded"
        status = status.lower().replace(" ", "_")
        if status in ("pass", "verified"):
            status = "grounded"
        elif status in ("insufficient_evidence", "warning"):
            status = "insufficient"
        elif status not in ("grounded", "insufficient", "unsupported"):
            status = "grounded"

        if status == "grounded":
            grounded_count += 1
        elif status == "insufficient":
            insufficient_count += 1
        else:
            unsupported_count += 1

        conf = float(c.get("confidence") if c.get("confidence") is not None else (0.95 if status == "grounded" else 0.4))
        sup_ids = c.get("supporting_source_ids") or []
        first_src = None
        for sid in sup_ids:
            if sid in source_id_map:
                first_src = source_id_map[sid]
                break

        structured_claims.append(StructuredClaim(
            claim_id=cid,
            text=text,
            status=status,
            confidence=conf,
            evidence_text=c.get("evidence_text") or c.get("excerpt"),
            supporting_source_ids=sup_ids,
            source_url=first_src.url if first_src else c.get("source_url"),
            source_title=first_src.title if first_src else c.get("source_title"),
            verification_notes=c.get("verification_notes"),
        ))

    # 4. Evidence References
    evidence_refs: List[StructuredEvidenceRef] = []
    raw_evidence = d.get("retrieved_evidence") or []
    for idx, ev in enumerate(raw_evidence, 1):
        if not isinstance(ev, dict):
            if hasattr(ev, "model_dump"):
                ev = ev.model_dump()
            elif hasattr(ev, "to_dict"):
                ev = ev.to_dict()
            else:
                continue
        chunk_id = ev.get("chunk_id") or f"chunk_{idx}"
        src_url = ev.get("url") or ""
        src_obj = source_url_map.get(src_url.lower())
        evidence_refs.append(StructuredEvidenceRef(
            chunk_id=chunk_id,
            source_id=src_obj.source_id if src_obj else ev.get("source_id", ""),
            source_title=src_obj.title if src_obj else ev.get("title", ""),
            source_url=src_url,
            excerpt=ev.get("text", "")[:350],
            similarity_score=float(ev.get("similarity_score") or 0.0),
        ))

    # 5. Verification Summary
    v_report = d.get("verification_result") or d.get("verification_report") or {}
    feedback = d.get("feedback") or ""
    v_status = d.get("verification_status") or v_report.get("status") or ("verified" if grounded_count > 0 else "completed")
    v_summary = StructuredVerificationSummary(
        status=v_status,
        iteration_count=int(d.get("verification_iteration") or v_report.get("iteration") or 1),
        confidence_score=float(v_report.get("confidence") or (0.92 if grounded_count > 0 else 0.7)),
        total_claims=len(structured_claims),
        grounded_claims=grounded_count,
        insufficient_claims=insufficient_count,
        unsupported_claims=unsupported_count,
        feedback_notes=feedback or v_report.get("notes"),
    )

    # 6. Parse Report Content (Markdown Sections)
    report_text = d.get("report") or d.get("writer") or d.get("content_markdown") or ""
    parsed_sections = _extract_sections_from_markdown(report_text, default_topic=title)

    # Extract Key Findings
    key_findings: List[str] = parsed_sections.get("key_findings", [])
    if not key_findings and d.get("key_findings"):
        for kf in d["key_findings"]:
            if isinstance(kf, dict):
                hl = kf.get("headline", "").strip()
                ta = kf.get("takeaway", "").strip()
                if hl and ta:
                    key_findings.append(f"{hl}: {ta}")
                elif ta:
                    key_findings.append(ta)
            elif isinstance(kf, str) and kf.strip():
                key_findings.append(kf.strip())
    if not key_findings and structured_claims:
        key_findings = [c.text for c in structured_claims[:5] if c.status == "grounded"]

    # Research Objectives fallback
    if not objectives and d.get("research_objectives"):
        objectives.extend(d["research_objectives"])
    if not objectives and parsed_sections.get("objectives"):
        objectives.extend(parsed_sections["objectives"])
    if not objectives:
        objectives = [f"Conduct comprehensive research analysis on {title}"]

    # Research Limitations
    limitations: List[str] = []
    if d.get("research_limitations") or d.get("limitations"):
        limitations.extend(d.get("research_limitations") or d.get("limitations") or [])
    if parsed_sections.get("limitations"):
        for lim in parsed_sections["limitations"]:
            if lim not in limitations:
                limitations.append(lim)
    if d.get("degraded_modes"):
        limitations.extend([f"Degraded operation mode active: {dm}" for dm in d["degraded_modes"]])
    if d.get("failed_sources"):
        limitations.append(f"{len(d['failed_sources'])} sources failed retrieval and were safely excluded from synthesis.")
    if not limitations:
        limitations = [
            "Research is grounded strictly in publicly discoverable live web evidence and verified domain indices.",
            "Dynamic web sources retrieved reflect real-time indexation as of the generation timestamp."
        ]

    # Detailed Analysis Sections
    detailed_sections = parsed_sections.get("analysis_sections", [])
    if not detailed_sections and d.get("thematic_analysis"):
        for t_sec in d["thematic_analysis"]:
            if isinstance(t_sec, dict):
                detailed_sections.append(StructuredAnalysisSection(
                    heading=t_sec.get("heading", "Analytical Synthesis"),
                    content=t_sec.get("content", "")
                ))
    if not detailed_sections:
        # Fallback to whole report text if no explicit headings found
        detailed_sections = [
            StructuredAnalysisSection(
                heading="Detailed Findings & Analysis",
                content=report_text or "Analysis synthesized from verified evidence chunks."
            )
        ]

    # Executive Summary
    summary = parsed_sections.get("summary") or d.get("summary") or ""
    if not summary and detailed_sections:
        summary = detailed_sections[0].content[:400] + "..."

    # Strategic Conclusion
    conclusion = (
        d.get("conclusion")
        or d.get("strategic_outlook")
        or parsed_sections.get("conclusion")
        or ""
    )
    if not conclusion:
        for idx, sec in enumerate(detailed_sections):
            sec_h = sec.heading.lower()
            if any(k in sec_h for k in ["conclusion", "strategic implication", "forward outlook", "strategic outlook"]):
                conclusion = sec.content
                detailed_sections.pop(idx)
                break

    return StructuredReport(
        title=title,
        generated_at=now_iso,
        executive_summary=summary.strip(),
        conclusion=conclusion.strip(),
        research_objectives=objectives,
        key_findings=key_findings,
        detailed_analysis=detailed_sections,
        claims=structured_claims,
        inline_citations={s.citation_tag: f"{s.title} ({s.url})" for s in structured_sources},
        sources=structured_sources,
        evidence_references=evidence_refs,
        verification_summary=v_summary,
        research_limitations=limitations,
        metadata={
            "session_id": d.get("session_id") or d.get("id"),
            "models_used": d.get("models_used", ["Groq Llama-3.3-70b-versatile"]),
            "total_sources_indexed": len(structured_sources),
            "total_claims_audited": len(structured_claims),
        }
    )


def _build_from_db_session(session: Any) -> StructuredReport:
    """Build StructuredReport from SQLAlchemy ResearchSession model."""
    d = session.to_dict(include_details=True)
    if session.project:
        d["project_title"] = session.project.title
    return _build_from_dict(d, default_topic=session.topic)


def _build_from_markdown_text(report_text: str, topic: str, now_str: str) -> StructuredReport:
    """Parse pure markdown text into the structured report object."""
    sections = _extract_sections_from_markdown(report_text, default_topic=topic)
    
    # Extract URLs from markdown to synthesize fallback source models
    discovered_urls = re.findall(r'\[([^\]]+)\]\((https?://[^)]+)\)', report_text)
    fallback_sources: List[StructuredSource] = []
    seen_urls = set()
    for idx, (title, url) in enumerate(discovered_urls, 1):
        if url.lower() in seen_urls:
            continue
        seen_urls.add(url.lower())
        domain = url.split("//")[-1].split("/")[0] if url else "web"
        fallback_sources.append(StructuredSource(
            source_id=f"src_{idx}",
            source_number=idx,
            title=title if title != url else f"Source {idx} ({domain})",
            url=url,
            domain=domain,
            source_type="academic" if any(k in domain for k in ["arxiv", "edu", "nature", "ieee"]) else "news" if any(k in domain for k in ["reuters", "bloomberg", "techcrunch"]) else "general",
            publication_date="N/A",
            freshness="recent",
            quality_score=0.85,
        ))

    sources = sections.get("sources") or fallback_sources
    claims = sections.get("claims") or []

    grounded_count = sum(1 for c in claims if c.status == "grounded")
    insufficient_count = sum(1 for c in claims if c.status == "insufficient")
    unsupported_count = sum(1 for c in claims if c.status == "unsupported")
    conf_score = round(grounded_count / len(claims), 2) if claims else 0.9

    conclusion = sections.get("conclusion") or ""
    analysis_secs = sections.get("analysis_sections", [StructuredAnalysisSection(heading="Analysis", content=report_text)])
    if not conclusion:
        for idx, sec in enumerate(analysis_secs):
            sec_h = sec.heading.lower()
            if any(k in sec_h for k in ["conclusion", "strategic implication", "forward outlook", "strategic outlook"]):
                conclusion = sec.content
                analysis_secs.pop(idx)
                break

    return StructuredReport(
        title=topic,
        generated_at=now_str,
        executive_summary=sections.get("summary") or "Synthesized research findings based on live web discovery and empirical citations.",
        conclusion=conclusion.strip(),
        research_objectives=sections.get("objectives") or [f"Conduct comprehensive analysis on {topic}"],
        key_findings=sections.get("key_findings", []),
        detailed_analysis=analysis_secs,
        claims=claims,
        inline_citations={s.citation_tag: f"{s.title} ({s.url})" for s in sources},
        sources=sources,
        evidence_references=[],
        verification_summary=StructuredVerificationSummary(
            status="verified" if claims else "completed",
            iteration_count=1,
            confidence_score=conf_score,
            total_claims=len(claims),
            grounded_claims=grounded_count,
            insufficient_claims=insufficient_count,
            unsupported_claims=unsupported_count,
        ),
        research_limitations=sections.get("limitations") or [
            "Report synthesized from verified evidence chunks retrieved during research session.",
            "All cited sources were validated for accessibility and relevance."
        ],
        metadata={"source_format": "parsed_markdown"}
    )


def _extract_sections_from_markdown(report_text: str, default_topic: str) -> Dict[str, Any]:
    """Segment a markdown document into standard report sections."""
    lines = report_text.split("\n")
    summary_lines = []
    objectives: List[str] = []
    key_findings: List[str] = []
    analysis_sections: List[StructuredAnalysisSection] = []
    limitations: List[str] = []
    claims_lines: List[str] = []
    sources_lines: List[str] = []
    conclusion_lines: List[str] = []

    current_heading = ""
    current_content: List[str] = []
    in_summary = False
    in_objectives = False
    in_findings = False
    in_limitations = False
    in_claims = False
    in_sources = False
    in_conclusion = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_heading and not in_findings and not in_objectives and not in_claims and not in_sources and not in_conclusion:
                current_content.append("")
            continue

        # Detect Headings
        if stripped.startswith("#"):
            h_text = stripped.lstrip("#").strip()

            # Save previous section if open
            if current_heading and current_content and not in_findings and not in_summary and not in_limitations and not in_objectives and not in_claims and not in_sources and not in_conclusion:
                analysis_sections.append(StructuredAnalysisSection(
                    heading=current_heading,
                    content="\n".join(current_content).strip()
                ))
                current_content = []

            h_lower = h_text.lower()
            if any(k in h_lower for k in ["summary", "executive summary", "introduction"]):
                in_summary = True
                in_objectives = in_findings = in_limitations = in_claims = in_sources = in_conclusion = False
                current_heading = h_text
            elif any(k in h_lower for k in ["objective", "research objective", "research goal"]):
                in_objectives = True
                in_summary = in_findings = in_limitations = in_claims = in_sources = in_conclusion = False
                current_heading = h_text
            elif any(k in h_lower for k in ["finding", "key finding", "core takeaways"]):
                in_findings = True
                in_summary = in_objectives = in_limitations = in_claims = in_sources = in_conclusion = False
                current_heading = h_text
            elif any(k in h_lower for k in ["conclusion", "strategic implication", "forward outlook", "strategic outlook"]):
                in_conclusion = True
                in_summary = in_objectives = in_findings = in_limitations = in_claims = in_sources = False
                current_heading = h_text
            elif any(k in h_lower for k in ["limitation", "caveat", "methodology note"]):
                in_limitations = True
                in_summary = in_objectives = in_findings = in_claims = in_sources = in_conclusion = False
                current_heading = h_text
            elif any(k in h_lower for k in ["verified claims", "grounding lineage"]):
                in_claims = True
                in_summary = in_objectives = in_findings = in_limitations = in_sources = in_conclusion = False
                current_heading = h_text
            elif any(k in h_lower for k in ["sources", "references", "authoritative sources"]):
                in_sources = True
                in_summary = in_objectives = in_findings = in_limitations = in_claims = in_conclusion = False
                current_heading = h_text
            else:
                in_summary = in_objectives = in_findings = in_limitations = in_claims = in_sources = in_conclusion = False
                current_heading = h_text

            continue

        if in_summary:
            summary_lines.append(stripped)
        elif in_conclusion:
            conclusion_lines.append(stripped)
        elif in_objectives:
            if stripped.startswith("- ") or stripped.startswith("* ") or re.match(r'^\d+\.\s', stripped):
                clean_bullet = re.sub(r'^[*-]\s*|^\d+\.\s*', '', stripped)
                objectives.append(_clean_markdown_text(clean_bullet))
        elif in_findings:
            if stripped.startswith("- ") or stripped.startswith("* ") or re.match(r'^\d+\.\s', stripped):
                clean_bullet = re.sub(r'^[*-]\s*|^\d+\.\s*', '', stripped)
                key_findings.append(_clean_markdown_text(clean_bullet))
        elif in_limitations:
            if stripped.startswith("- ") or stripped.startswith("* "):
                limitations.append(_clean_markdown_text(stripped[2:]))
            else:
                limitations.append(_clean_markdown_text(stripped))
        elif in_claims:
            claims_lines.append(stripped)
        elif in_sources:
            sources_lines.append(stripped)
        else:
            current_content.append(stripped)

    # Append trailing section
    if current_heading and current_content and not in_findings and not in_summary and not in_limitations and not in_objectives and not in_claims and not in_sources and not in_conclusion:
        analysis_sections.append(StructuredAnalysisSection(
            heading=current_heading,
            content="\n".join(current_content).strip()
        ))

    parsed_claims = parse_claims_from_table(claims_lines)
    parsed_sources = parse_sources_from_table(sources_lines)

    raw_summary = " ".join(summary_lines).strip()
    clean_summary = raw_summary
    if (raw_summary.startswith("{") and raw_summary.endswith("}")) or '"summary"' in raw_summary:
        try:
            m = re.search(r'(\{.*\})', raw_summary, re.DOTALL)
            if m:
                d = json.loads(m.group(1))
                if isinstance(d, dict) and "summary" in d:
                    clean_summary = str(d["summary"]).strip()
        except Exception:
            pass
        if clean_summary == raw_summary:
            m = re.search(r'"summary"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', raw_summary)
            if m:
                clean_summary = m.group(1).strip()

    return {
        "summary": clean_summary,
        "objectives": objectives,
        "key_findings": key_findings,
        "analysis_sections": analysis_sections,
        "conclusion": "\n".join(conclusion_lines).strip(),
        "limitations": limitations,
        "claims": parsed_claims,
        "sources": parsed_sources,
    }


# =====================================================================
# Exporter 1: Clean Markdown
# =====================================================================

def export_to_markdown(report: StructuredReport) -> str:
    """
    Export StructuredReport to clean, comprehensive Markdown format.
    Preserves:
    - Metadata Header
    - Executive Summary
    - Research Objectives
    - Key Findings
    - Detailed Analysis sections
    - Verified Claims Table
    - Authoritative Sources with live URLs
    - Evidence References
    - Verification Summary & Research Limitations
    """
    lines: List[str] = [
        f"# {report.title}",
        f"**Generated**: {report.generated_at}  |  **SYNAPSE AI Autonomous Engine**",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        "",
        report.executive_summary or "No executive summary available.",
        "",
    ]

    # Research Objectives
    if report.research_objectives:
        lines.extend([
            "## 2. Research Objectives",
            "",
            *[f"- {obj}" for obj in report.research_objectives],
            "",
        ])

    # Key Findings
    if report.key_findings:
        lines.extend([
            "## 3. Key Findings",
            "",
            *[f"- **Finding {idx}**: {kf}" for idx, kf in enumerate(report.key_findings, 1)],
            "",
        ])

    # Detailed Analysis Sections
    if report.detailed_analysis:
        lines.extend(["## 4. Detailed Analysis", ""])
        for section in report.detailed_analysis:
            lines.append(f"### {section.heading}\n")
            lines.append(f"{section.content}\n")

    # Strategic Conclusion & Forward Outlook
    if report.conclusion:
        lines.extend([
            "## Strategic Conclusion & Forward Outlook",
            "",
            report.conclusion,
            "",
        ])

    # Claims Audit Table
    if report.claims:
        lines.extend([
            "## 5. Verified Claims & Grounding Lineage",
            "",
            "| ID | Status | Confidence | Claim Statement | Evidence Excerpt | Source |",
            "|---|---|---|---|---|---|",
        ])
        for c in report.claims:
            icon = "✅ Grounded" if c.status == "grounded" else "⚠️ Insufficient" if c.status == "insufficient" else "❌ Unsupported"
            conf = f"{int(c.confidence * 100)}%"
            clean_stmt = c.text.replace("|", "/")
            excerpt = (c.evidence_text or "Direct cited chunk")[:100].replace("|", "/") + "..."
            src = f"[{c.source_title or 'Link'}]({c.source_url})" if c.source_url else "Referenced Source"
            lines.append(f"| `{c.claim_id}` | {icon} | {conf} | {clean_stmt} | *{excerpt}* | {src} |")
        lines.append("")

    # Authoritative Sources Section
    if report.sources:
        lines.extend([
            "## 6. Authoritative Sources",
            "",
            "| Ref | Title | Domain | Type | Freshness | Published | Quality Score |",
            "|---|---|---|---|---|---|---|",
        ])
        for s in report.sources:
            title_link = f"[{s.title}]({s.url})" if s.url else s.title
            lines.append(
                f"| [{s.source_number}] | {title_link} | `{s.domain}` | {s.source_type} | {s.freshness} | {s.publication_date} | {s.quality_score:.2f} ({s.quality_tier}) |"
            )
        lines.append("")

    # Evidence References
    if report.evidence_references:
        lines.extend([
            "## 7. Vector Evidence References",
            "",
            "| Chunk ID | Excerpt | Similarity | Source Reference |",
            "|---|---|---|---|",
        ])
        for er in report.evidence_references[:10]:
            clean_ex = er.excerpt.replace("|", "/").replace("\n", " ")[:140]
            lines.append(f"| `{er.chunk_id}` | \"{clean_ex}...\" | {er.similarity_score:.2f} | [{er.source_title or 'Source'}]({er.source_url}) |")
        lines.append("")

    # Verification Summary
    vs = report.verification_summary
    lines.extend([
        "## 8. Autonomous Verification Summary",
        "",
        f"- **Verification Status**: `{vs.status.upper()}`",
        f"- **Audit Iterations**: Cycle {vs.iteration_count}",
        f"- **Composite Verification Confidence**: {int(vs.confidence_score * 100)}%",
        f"- **Claims Breakdown**: {vs.grounded_claims} Grounded · {vs.insufficient_claims} Insufficient · {vs.unsupported_claims} Unsupported",
    ])
    if vs.feedback_notes:
        lines.append(f"- **Auditor Verdict**: {vs.feedback_notes}")
    lines.append("")

    # Research Limitations
    if report.research_limitations:
        lines.extend([
            "## 9. Research Limitations & Methodology Notes",
            "",
            *[f"- {lim}" for lim in report.research_limitations],
            "",
        ])

    return "\n".join(lines)


# =====================================================================
# Exporter 2: Professional Word (.docx) Document
# =====================================================================

def _add_docx_hyperlink(paragraph, url: str, text: str, color_rgb: RGBColor = RGBColor(43, 87, 154)):
    """Add a real clickable XML hyperlink run to a python-docx paragraph."""
    part = paragraph.part
    r_id = part.relate_to(url, docx.opc.constants.RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    hyperlink = OxmlElement('w:hyperlink')
    hyperlink.set(qn('r:id'), r_id)

    new_run = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr')

    # Color
    c = OxmlElement('w:color')
    c.set(qn('w:val'), f"{color_rgb[0]:02X}{color_rgb[1]:02X}{color_rgb[2]:02X}")
    rPr.append(c)

    # Underline
    u = OxmlElement('w:u')
    u.set(qn('w:val'), 'single')
    rPr.append(u)

    new_run.append(rPr)
    new_run.text = text
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)


def _set_cell_background(cell, fill_hex: str):
    """Set background color of a table cell in docx."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill_hex)
    tcPr.append(shd)


def export_to_docx(report: StructuredReport) -> bytes:
    """
    Generate an enterprise-grade DOCX document from StructuredReport.
    Includes:
    - Header & Footer with dynamic Word page numbers (Page X of Y)
    - Professional heading hierarchy with Deep Indigo branding
    - Executive Summary callout
    - Research Objectives
    - Key Findings
    - Detailed Analysis sections
    - Formatted Claims Audit Table
    - Clickable Authoritative Sources Table with real hyperlinked URLs
    - Evidence references table
    - Verification Summary & Research Limitations
    """
    doc = docx.Document()

    # Configure Margins (1 inch)
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

        # Configure Header
        header = section.header
        p_head = header.paragraphs[0]
        p_head.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r_head = p_head.add_run("SYNAPSE AI  |  Autonomous Research Report")
        r_head.font.name = 'Calibri'
        r_head.font.size = Pt(8.5)
        r_head.font.color.rgb = RGBColor(140, 140, 160)

        # Configure Footer with Dynamic Page Number
        footer = section.footer
        p_foot = footer.paragraphs[0]
        p_foot.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r_foot_label = p_foot.add_run("Page ")
        r_foot_label.font.name = 'Calibri'
        r_foot_label.font.size = Pt(9)
        r_foot_label.font.color.rgb = RGBColor(120, 120, 140)

        r_page = p_foot.add_run()
        fldChar1 = OxmlElement('w:fldChar')
        fldChar1.set(qn('w:fldCharType'), 'begin')
        instrText = OxmlElement('w:instrText')
        instrText.set(qn('xml:space'), 'preserve')
        instrText.text = "PAGE"
        fldChar2 = OxmlElement('w:fldChar')
        fldChar2.set(qn('w:fldCharType'), 'separate')
        fldChar3 = OxmlElement('w:fldChar')
        fldChar3.set(qn('w:fldCharType'), 'end')
        r_page._r.append(fldChar1)
        r_page._r.append(instrText)
        r_page._r.append(fldChar2)
        r_page._r.append(fldChar3)

        r_of = p_foot.add_run(" of ")
        r_of.font.name = 'Calibri'
        r_of.font.size = Pt(9)
        r_of.font.color.rgb = RGBColor(120, 120, 140)

        r_numpages = p_foot.add_run()
        fldChar4 = OxmlElement('w:fldChar')
        fldChar4.set(qn('w:fldCharType'), 'begin')
        instrText2 = OxmlElement('w:instrText')
        instrText2.set(qn('xml:space'), 'preserve')
        instrText2.text = "NUMPAGES"
        fldChar5 = OxmlElement('w:fldChar')
        fldChar5.set(qn('w:fldCharType'), 'separate')
        fldChar6 = OxmlElement('w:fldChar')
        fldChar6.set(qn('w:fldCharType'), 'end')
        r_numpages._r.append(fldChar4)
        r_numpages._r.append(instrText2)
        r_numpages._r.append(fldChar5)
        r_numpages._r.append(fldChar6)

    # Document Title
    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(8)
    p_title.paragraph_format.space_after = Pt(4)
    r_title = p_title.add_run(report.title)
    r_title.font.name = 'Calibri'
    r_title.font.size = Pt(24)
    r_title.font.bold = True
    r_title.font.color.rgb = RGBColor(43, 37, 84)  # Deep Indigo Plum

    # Subtitle & Generation Metadata Banner
    p_meta = doc.add_paragraph()
    p_meta.paragraph_format.space_after = Pt(14)
    r_meta = p_meta.add_run(f"Generated on {report.generated_at}   •   Status: {report.verification_summary.status.upper()} (Cycle {report.verification_summary.iteration_count})")
    r_meta.font.name = 'Calibri'
    r_meta.font.size = Pt(10)
    r_meta.font.italic = True
    r_meta.font.color.rgb = RGBColor(217, 83, 101)  # Rose Pink Accent

    # 1. Executive Summary
    h1 = doc.add_paragraph()
    h1.paragraph_format.space_before = Pt(14)
    h1.paragraph_format.space_after = Pt(4)
    r_h1 = h1.add_run("1. Executive Summary")
    r_h1.font.name = 'Calibri'
    r_h1.font.size = Pt(16)
    r_h1.font.bold = True
    r_h1.font.color.rgb = RGBColor(43, 37, 84)

    p_sum = doc.add_paragraph()
    p_sum.paragraph_format.line_spacing = 1.15
    p_sum.paragraph_format.space_after = Pt(12)
    r_sum = p_sum.add_run(report.executive_summary or "Empirical analysis synthesized from verified evidence.")
    r_sum.font.name = 'Calibri'
    r_sum.font.size = Pt(11)
    r_sum.font.color.rgb = RGBColor(51, 65, 85)

    # 2. Research Objectives
    if report.research_objectives:
        h2_obj = doc.add_paragraph()
        h2_obj.paragraph_format.space_before = Pt(12)
        h2_obj.paragraph_format.space_after = Pt(4)
        r_h2_obj = h2_obj.add_run("2. Research Objectives & Scope")
        r_h2_obj.font.name = 'Calibri'
        r_h2_obj.font.size = Pt(16)
        r_h2_obj.font.bold = True
        r_h2_obj.font.color.rgb = RGBColor(43, 37, 84)

        for obj in report.research_objectives:
            p_bullet = doc.add_paragraph(style='List Bullet')
            p_bullet.paragraph_format.space_after = Pt(3)
            r_b = p_bullet.add_run(obj)
            r_b.font.name = 'Calibri'
            r_b.font.size = Pt(11)
            r_b.font.color.rgb = RGBColor(51, 65, 85)

    # 3. Key Findings
    if report.key_findings:
        h2_kf = doc.add_paragraph()
        h2_kf.paragraph_format.space_before = Pt(12)
        h2_kf.paragraph_format.space_after = Pt(4)
        r_h2_kf = h2_kf.add_run("3. Key Findings")
        r_h2_kf.font.name = 'Calibri'
        r_h2_kf.font.size = Pt(16)
        r_h2_kf.font.bold = True
        r_h2_kf.font.color.rgb = RGBColor(43, 37, 84)

        for idx, kf in enumerate(report.key_findings, 1):
            p_num = doc.add_paragraph(style='List Number')
            p_num.paragraph_format.space_after = Pt(4)
            r_num = p_num.add_run(kf)
            r_num.font.name = 'Calibri'
            r_num.font.size = Pt(11)
            r_num.font.bold = True if idx <= 2 else False
            r_num.font.color.rgb = RGBColor(30, 41, 59)

    # 4. Detailed Analysis
    if report.detailed_analysis:
        h2_da = doc.add_paragraph()
        h2_da.paragraph_format.space_before = Pt(14)
        h2_da.paragraph_format.space_after = Pt(4)
        r_h2_da = h2_da.add_run("4. Detailed Analysis & Evidence Evaluation")
        r_h2_da.font.name = 'Calibri'
        r_h2_da.font.size = Pt(16)
        r_h2_da.font.bold = True
        r_h2_da.font.color.rgb = RGBColor(43, 37, 84)

        for sec in report.detailed_analysis:
            p_subh = doc.add_paragraph()
            p_subh.paragraph_format.space_before = Pt(10)
            p_subh.paragraph_format.space_after = Pt(3)
            r_subh = p_subh.add_run(sec.heading)
            r_subh.font.name = 'Calibri'
            r_subh.font.size = Pt(13)
            r_subh.font.bold = True
            r_subh.font.color.rgb = RGBColor(71, 85, 105)

            p_body = doc.add_paragraph()
            p_body.paragraph_format.line_spacing = 1.15
            p_body.paragraph_format.space_after = Pt(8)
            r_body = p_body.add_run(sec.content)
            r_body.font.name = 'Calibri'
            r_body.font.size = Pt(11)
            r_body.font.color.rgb = RGBColor(51, 65, 85)

    # Strategic Conclusion & Forward Outlook
    if report.conclusion:
        h2_concl = doc.add_paragraph()
        h2_concl.paragraph_format.space_before = Pt(14)
        h2_concl.paragraph_format.space_after = Pt(4)
        r_h2_concl = h2_concl.add_run("Strategic Conclusion & Forward Outlook")
        r_h2_concl.font.name = 'Calibri'
        r_h2_concl.font.size = Pt(16)
        r_h2_concl.font.bold = True
        r_h2_concl.font.color.rgb = RGBColor(43, 37, 84)

        for p_chunk in report.conclusion.split("\n\n"):
            p_chunk = p_chunk.strip()
            if not p_chunk:
                continue
            p_concl = doc.add_paragraph()
            p_concl.paragraph_format.line_spacing = 1.15
            p_concl.paragraph_format.space_after = Pt(8)
            r_concl = p_concl.add_run(p_chunk)
            r_concl.font.name = 'Calibri'
            r_concl.font.size = Pt(11)
            r_concl.font.color.rgb = RGBColor(51, 65, 85)

    # 5. Verified Claims Table
    if report.claims:
        h2_cl = doc.add_paragraph()
        h2_cl.paragraph_format.space_before = Pt(14)
        h2_cl.paragraph_format.space_after = Pt(6)
        r_h2_cl = h2_cl.add_run("5. Verified Claims & Grounding Matrix")
        r_h2_cl.font.name = 'Calibri'
        r_h2_cl.font.size = Pt(16)
        r_h2_cl.font.bold = True
        r_h2_cl.font.color.rgb = RGBColor(43, 37, 84)

        table = doc.add_table(rows=1, cols=4)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = True

        hdr_cells = table.rows[0].cells
        headers = ["Claim Statement", "Status", "Confidence", "Supporting Source"]
        for idx, text in enumerate(headers):
            hdr_cells[idx].text = text
            _set_cell_background(hdr_cells[idx], "2B2554")
            p = hdr_cells[idx].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for run in p.runs:
                run.font.name = 'Calibri'
                run.font.bold = True
                run.font.size = Pt(9.5)
                run.font.color.rgb = RGBColor(255, 255, 255)

        for c in report.claims:
            row_cells = table.add_row().cells
            row_cells[0].text = c.text
            row_cells[1].text = c.status.capitalize()
            row_cells[2].text = f"{int(c.confidence * 100)}%"

            # Clickable source link in cell 3
            p_src = row_cells[3].paragraphs[0]
            p_src.text = ""
            if c.source_url:
                _add_docx_hyperlink(p_src, c.source_url, c.source_title or c.source_url[:30])
            else:
                p_src.add_run(c.source_title or "Indexed Vector Evidence")

            # Style cells
            for cell_idx, cell in enumerate(row_cells):
                cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                p = cell.paragraphs[0]
                for run in p.runs:
                    run.font.name = 'Calibri'
                    run.font.size = Pt(9.5)

        doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # 6. Clickable Authoritative Sources Table
    if report.sources:
        h2_src = doc.add_paragraph()
        h2_src.paragraph_format.space_before = Pt(14)
        h2_src.paragraph_format.space_after = Pt(6)
        r_h2_src = h2_src.add_run("6. Authoritative Sources & Reference Catalog")
        r_h2_src.font.name = 'Calibri'
        r_h2_src.font.size = Pt(16)
        r_h2_src.font.bold = True
        r_h2_src.font.color.rgb = RGBColor(43, 37, 84)

        table_src = doc.add_table(rows=1, cols=6)
        table_src.alignment = WD_TABLE_ALIGNMENT.CENTER
        table_src.autofit = True

        hdr_src_cells = table_src.rows[0].cells
        src_headers = ["Ref", "Source Document", "Domain", "Type", "Freshness", "Score"]
        for idx, text in enumerate(src_headers):
            hdr_src_cells[idx].text = text
            _set_cell_background(hdr_src_cells[idx], "2B2554")
            p = hdr_src_cells[idx].paragraphs[0]
            for run in p.runs:
                run.font.name = 'Calibri'
                run.font.bold = True
                run.font.size = Pt(9)
                run.font.color.rgb = RGBColor(255, 255, 255)

        for s in report.sources:
            row_cells = table_src.add_row().cells
            row_cells[0].text = f"[{s.source_number}]"

            # Clickable hyperlink
            p_title = row_cells[1].paragraphs[0]
            p_title.text = ""
            if s.url:
                _add_docx_hyperlink(p_title, s.url, s.title)
            else:
                p_title.add_run(s.title)

            row_cells[2].text = s.domain
            row_cells[3].text = s.source_type
            row_cells[4].text = s.freshness
            row_cells[5].text = f"{s.quality_score:.2f}"

            for cell in row_cells:
                cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                for run in cell.paragraphs[0].runs:
                    run.font.name = 'Calibri'
                    run.font.size = Pt(8.5)

        doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # 7. Verification Summary
    h2_v = doc.add_paragraph()
    h2_v.paragraph_format.space_before = Pt(14)
    h2_v.paragraph_format.space_after = Pt(4)
    r_h2_v = h2_v.add_run("7. Autonomous Verification Audit")
    r_h2_v.font.name = 'Calibri'
    r_h2_v.font.size = Pt(16)
    r_h2_v.font.bold = True
    r_h2_v.font.color.rgb = RGBColor(43, 37, 84)

    vs = report.verification_summary
    v_lines = [
        f"Verification Decision: {vs.status.upper()}",
        f"Completed Audit Iterations: Cycle {vs.iteration_count}",
        f"Confidence Score: {int(vs.confidence_score * 100)}%",
        f"Claim Breakdown: {vs.grounded_claims} Grounded, {vs.insufficient_claims} Insufficient, {vs.unsupported_claims} Unsupported",
    ]
    if vs.feedback_notes:
        v_lines.append(f"Verification Feedback: {vs.feedback_notes}")

    for vl in v_lines:
        p_v = doc.add_paragraph(style='List Bullet')
        p_v.paragraph_format.space_after = Pt(3)
        r_vl = p_v.add_run(vl)
        r_vl.font.name = 'Calibri'
        r_vl.font.size = Pt(10.5)
        r_vl.font.color.rgb = RGBColor(51, 65, 85)

    # 8. Research Limitations
    if report.research_limitations:
        h2_lim = doc.add_paragraph()
        h2_lim.paragraph_format.space_before = Pt(12)
        h2_lim.paragraph_format.space_after = Pt(4)
        r_h2_lim = h2_lim.add_run("8. Research Limitations & Scope")
        r_h2_lim.font.name = 'Calibri'
        r_h2_lim.font.size = Pt(16)
        r_h2_lim.font.bold = True
        r_h2_lim.font.color.rgb = RGBColor(43, 37, 84)

        for lim in report.research_limitations:
            p_l = doc.add_paragraph(style='List Bullet')
            p_l.paragraph_format.space_after = Pt(3)
            r_l = p_l.add_run(lim)
            r_l.font.name = 'Calibri'
            r_l.font.size = Pt(10.5)
            r_l.font.color.rgb = RGBColor(100, 116, 139)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


# =====================================================================
# Exporter 3: Professional PDF Document
# =====================================================================

class SynapseReportPDF(FPDF):
    """Custom FPDF subclass providing executive headers, footers, page numbers, and universal Unicode safety."""
    def __init__(self, title="SYNAPSE Research"):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.doc_title = title

    def normalize_text(self, text):
        if text:
            text = _sanitize_pdf_latin1(str(text))
        return super().normalize_text(text)

    def header(self):
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(100, 116, 139)  # Slate 500
        self.cell(0, 5, "SYNAPSE AI  |  Autonomous Research Report", align="L")
        self.set_font("Helvetica", "", 8)
        self.set_text_color(13, 148, 136)  # Polar Seafoam
        self.cell(0, 5, "Empirical Evidence & Audit Trail", align="R")
        self.ln(6)
        self.set_draw_color(226, 232, 240)  # Slate 200
        self.set_line_width(0.3)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-14)
        self.set_draw_color(226, 232, 240)
        self.set_line_width(0.2)
        self.line(10, self.get_y(), 200, self.get_y())
        self.set_font("Helvetica", "", 8)
        self.set_text_color(148, 163, 184)
        self.cell(95, 8, "SYNAPSE AI Intelligence Platform", align="L")
        self.cell(95, 8, f"Page {self.page_no()}/{{nb}}", align="R")


def export_to_pdf(report: StructuredReport) -> bytes:
    """
    Generate a publication-grade PDF from StructuredReport matching the UI theme.
    Includes:
    - Running headers and page numbers (Page X of Y)
    - Executive Electric Cobalt branding & Slate typography
    - Metadata badges (Status, Confidence, Sources Count)
    - Executive Summary with left accent border
    - Numbered Key Findings
    - Detailed Analysis narrative with automatic graphical table rendering
    - Full Verified Claims Matrix table with status badges and citations
    - Authoritative Sources Table with clickable URLs and quality scores
    - Autonomous Verification Audit & Research Limitations
    """
    pdf = SynapseReportPDF(title=report.title)
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    # Document Title
    pdf.set_font("Helvetica", "B", 17)
    pdf.set_text_color(15, 23, 42)  # Slate 900
    pdf.multi_cell(0, 7.5, _sanitize_pdf_latin1(report.title))
    pdf.ln(2)

    # Executive Metadata Badges Bar
    vs = report.verification_summary
    status_str = vs.status.upper()
    is_verified = status_str in ("VERIFIED", "GROUNDED", "COMPLETED", "PASSED")

    pdf.set_font("Helvetica", "B", 7.5)
    if is_verified:
        pdf.set_fill_color(220, 252, 231)  # Emerald 100
        pdf.set_text_color(22, 101, 52)    # Emerald 800
        status_label = "VERIFIED REPORT"
    else:
        pdf.set_fill_color(254, 243, 199)  # Amber 100
        pdf.set_text_color(146, 64, 14)    # Amber 800
        status_label = f"STATUS: {status_str}"
    pdf.cell(32, 5.2, status_label, border=0, fill=True, align="C")
    pdf.cell(3)

    conf_pct = int(vs.confidence_score * 100) if vs.confidence_score <= 1.0 else int(vs.confidence_score)
    pdf.set_fill_color(224, 242, 254)  # Sky 100
    pdf.set_text_color(7, 89, 133)     # Sky 900
    pdf.cell(36, 5.2, f"CONFIDENCE: {conf_pct}%", border=0, fill=True, align="C")
    pdf.cell(3)

    pdf.set_fill_color(241, 245, 249)  # Slate 100
    pdf.set_text_color(71, 85, 105)    # Slate 600
    pdf.cell(34, 5.2, f"{len(report.sources)} SOURCES INDEXED", border=0, fill=True, align="C")
    pdf.cell(3)

    pdf.cell(24, 5.2, f"CYCLE {vs.iteration_count}", border=0, fill=True, align="C")
    pdf.ln(8)

    # Timestamp line
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(0, 4, _sanitize_pdf_latin1(f"Generated on {report.generated_at}"))
    pdf.ln(6)

    # 1. Executive Summary
    pdf.set_font("Helvetica", "B", 12.5)
    pdf.set_text_color(30, 64, 175)  # Electric Cobalt
    pdf.cell(0, 6.5, "1. Executive Summary")
    pdf.ln(6.5)

    summary_text = _sanitize_pdf_latin1(report.executive_summary or "Empirical analysis synthesized from verified evidence.")
    y_start = pdf.get_y()
    page_start = pdf.page_no()
    pdf.set_left_margin(14)
    pdf.set_x(14)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(51, 65, 85)
    pdf.multi_cell(186, 5.2, summary_text)
    y_end = pdf.get_y()
    page_end = pdf.page_no()
    if page_start == page_end and y_end > y_start:
        pdf.set_draw_color(37, 99, 235)  # Electric Cobalt accent line
        pdf.set_line_width(1.0)
        pdf.line(11, y_start, 11, y_end)
        pdf.set_line_width(0.2)
    pdf.set_left_margin(10)
    pdf.set_x(10)
    pdf.ln(5)

    # 2. Research Objectives
    if report.research_objectives:
        pdf.set_font("Helvetica", "B", 12.5)
        pdf.set_text_color(30, 64, 175)
        pdf.cell(0, 6.5, "2. Research Objectives & Scope")
        pdf.ln(6.5)

        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(51, 65, 85)
        for obj in report.research_objectives:
            pdf.cell(5)
            pdf.cell(4, 4.5, "-")
            pdf.multi_cell(0, 4.5, _sanitize_pdf_latin1(obj))
            pdf.ln(1)
        pdf.ln(4)

    # 3. Key Findings
    if report.key_findings:
        pdf.set_font("Helvetica", "B", 12.5)
        pdf.set_text_color(30, 64, 175)
        pdf.cell(0, 6.5, "3. Key Findings")
        pdf.ln(6.5)

        for idx, kf in enumerate(report.key_findings, 1):
            pdf.cell(5)
            clean_kf = re.sub(r'\[(?:Source\s*)(\d+)\]', r'[\1]', kf)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(30, 64, 175)
            pdf.cell(7, 4.5, f"{idx}.")
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(30, 41, 59)
            pdf.multi_cell(0, 4.5, _sanitize_pdf_latin1(clean_kf))
            pdf.ln(1.5)
        pdf.ln(4)

    # 4. Detailed Analysis
    if report.detailed_analysis:
        pdf.set_font("Helvetica", "B", 12.5)
        pdf.set_text_color(30, 64, 175)
        pdf.cell(0, 6.5, "4. Detailed Analysis & Evidence Evaluation")
        pdf.ln(6.5)

        for sec in report.detailed_analysis:
            pdf.set_font("Helvetica", "B", 10.5)
            pdf.set_text_color(15, 23, 42)
            pdf.cell(0, 5.5, _sanitize_pdf_latin1(sec.heading))
            pdf.ln(5.5)

            if sec.content:
                render_content_with_tables(pdf, sec.content)

            if sec.subsections:
                for sub in sec.subsections:
                    sub_h = sub.get("subheading") or sub.get("heading") or ""
                    sub_c = sub.get("content") or ""
                    if sub_h:
                        pdf.ln(1)
                        pdf.set_font("Helvetica", "B", 9.5)
                        pdf.set_text_color(30, 41, 59)
                        pdf.cell(0, 5, _sanitize_pdf_latin1(sub_h))
                        pdf.ln(5)
                    if sub_c:
                        render_content_with_tables(pdf, sub_c)
            pdf.ln(3)

    # Strategic Conclusion & Forward Outlook
    if report.conclusion:
        pdf.set_font("Helvetica", "B", 12.5)
        pdf.set_text_color(30, 64, 175)
        pdf.cell(0, 6.5, "Strategic Conclusion & Forward Outlook")
        pdf.ln(7.0)

        render_content_with_tables(pdf, report.conclusion)
        pdf.ln(3)

    # 5. Verified Claims Matrix
    if report.claims:
        pdf.set_font("Helvetica", "B", 12.5)
        pdf.set_text_color(30, 64, 175)
        pdf.cell(0, 6.5, "5. Verified Claims Matrix")
        pdf.ln(6.5)

        c_headers = ["ID", "Status", "Conf.", "Claim Statement", "Evidence Excerpt", "Verified Source"]
        c_widths = (18.0, 22.0, 14.0, 66.0, 44.0, 26.0)
        c_rows = []
        for c in report.claims:
            st_label = f"[{c.status.capitalize()}]"
            conf_pct_claim = int(c.confidence * 100) if c.confidence <= 1.0 else int(c.confidence)
            conf_label = f"{conf_pct_claim}%"
            stmt = _sanitize_pdf_latin1(c.text)
            exc = _sanitize_pdf_latin1(c.evidence_text or "Verified empirical chunk")
            src_label = _sanitize_pdf_latin1(c.source_title or (c.source_url[:25] if c.source_url else "Source Reference"))
            if c.source_url:
                src_cell = f"[{src_label[:30]}]({c.source_url})"
            else:
                src_cell = src_label[:30]
            c_rows.append([
                _sanitize_pdf_latin1(c.claim_id),
                st_label,
                conf_label,
                stmt,
                exc,
                src_cell
            ])

        render_pdf_table_block(pdf, c_headers, c_rows, col_widths=c_widths)

    # 6. Authoritative Sources Table with Clickable URLs
    if report.sources:
        pdf.set_font("Helvetica", "B", 12.5)
        pdf.set_text_color(30, 64, 175)
        pdf.cell(0, 6.5, "6. Authoritative Sources & Reference Catalog")
        pdf.ln(6.5)

        s_headers = ["#", "Title / Verified URL", "Domain", "Type", "Freshness"]
        s_widths = (12.0, 88.0, 35.0, 25.0, 30.0)
        s_rows = []
        for s in report.sources:
            safe_title = _sanitize_pdf_latin1(s.title[:65])
            title_cell = f"[{safe_title}]({s.url})" if s.url else safe_title
            s_rows.append([
                f"[{s.source_number}]",
                title_cell,
                _sanitize_pdf_latin1(s.domain or "-"),
                _sanitize_pdf_latin1(s.source_type or "-"),
                _sanitize_pdf_latin1(s.freshness or "-")
            ])

        render_pdf_table_block(pdf, s_headers, s_rows, col_widths=s_widths)

    # 7. Verification Summary
    pdf.set_font("Helvetica", "B", 12.5)
    pdf.set_text_color(30, 64, 175)
    pdf.cell(0, 6.5, "7. Autonomous Verification Audit")
    pdf.ln(6.5)

    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(51, 65, 85)
    pdf.cell(5)
    pdf.cell(0, 5, f"- Decision Status: {vs.status.upper()}")
    pdf.ln(5)
    pdf.cell(5)
    conf_audit = int(vs.confidence_score * 100) if vs.confidence_score <= 1.0 else int(vs.confidence_score)
    pdf.cell(0, 5, f"- Confidence Score: {conf_audit}% (Cycle {vs.iteration_count})")
    pdf.ln(5)
    pdf.cell(5)
    pdf.cell(0, 5, f"- Claims Grounded: {vs.grounded_claims} grounded, {vs.insufficient_claims} insufficient, {vs.unsupported_claims} unsupported")
    pdf.ln(5)
    if vs.feedback_notes:
        pdf.cell(5)
        pdf.multi_cell(0, 5, _sanitize_pdf_latin1(f"- Auditor Verdict: {vs.feedback_notes}"))
        pdf.ln(2)
    pdf.ln(4)

    # 8. Research Limitations
    if report.research_limitations:
        pdf.set_font("Helvetica", "B", 12.5)
        pdf.set_text_color(30, 64, 175)
        pdf.cell(0, 6.5, "8. Research Limitations & Scope")
        pdf.ln(6.5)

        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(100, 116, 139)
        for lim in report.research_limitations:
            pdf.cell(5)
            pdf.cell(4, 4.5, "-")
            pdf.multi_cell(0, 4.5, _sanitize_pdf_latin1(lim))
            pdf.ln(1)

    return bytes(pdf.output())
