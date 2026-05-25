import io, os, re, json, base64
from typing import List, Optional
from urllib.parse import quote

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Query
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Provation Barcode Label Generator - A4 8/Page AI")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
ASSET_DIR = os.path.join(BASE_DIR, "assets")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

NAME_RE = re.compile(r"\b[A-Z]{2,8}-[A-Z0-9][A-Z0-9-]{1,45}\b")
FH_RE = re.compile(r"\bFH\s*\d{5,8}\b", re.I)
SERIAL_RE = re.compile(r"\bWA\d{2}[A-Z0-9]{5,12}\b", re.I)
MAC_RE = re.compile(r"\b(?:[A-F0-9]{12}|(?:[A-F0-9]{2}[:-]){5}[A-F0-9]{2})\b", re.I)

class Label(BaseModel):
    location: Optional[str] = ""
    name: str = ""
    fh: Optional[str] = ""
    serial: Optional[str] = ""
    mac: Optional[str] = ""
    confidence: Optional[float] = None
    notes: Optional[str] = ""

class LabelsPayload(BaseModel):
    labels: List[Label]


def clean_name(s: str) -> str:
    s = str(s or "").strip().upper()
    s = s.replace("–", "-").replace("—", "-").replace("_", "-")
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[^A-Z0-9-]", "", s)
    # OCR fixes only after dash when next char is numeric.
    s = re.sub(r"(?<=-)O(?=\d)", "0", s)
    return s


def clean_fh(s: str) -> str:
    s = str(s or "").strip().upper().replace(" ", "").replace("-", "")
    if not s:
        return ""
    s = s.replace("FHI", "FH1").replace("FHO", "FH0")
    if not s.startswith("FH"):
        s = "FH" + s
    rest = s[2:].translate(str.maketrans({"O":"0","I":"1","L":"1","S":"5","B":"8","G":"6","Z":"2"}))
    rest = re.sub(r"\D", "", rest)
    return "FH" + rest if rest else ""


def clean_mac(s: str) -> str:
    return re.sub(r"[^A-F0-9]", "", str(s or "").upper())


def normalize_label(row: dict) -> dict:
    conf = row.get("confidence", None)
    try:
        conf = float(conf) if conf not in (None, "") else None
    except Exception:
        conf = None
    return {
        "location": str(row.get("location") or "").strip(),
        "name": clean_name(row.get("name") or row.get("neuron_name") or row.get("barcode_data") or ""),
        "fh": clean_fh(row.get("fh") or row.get("asset") or row.get("asset_number") or row.get("current_ecn") or ""),
        "serial": str(row.get("serial") or row.get("serial_number") or "").strip().upper(),
        "mac": clean_mac(row.get("mac") or row.get("mac_address") or ""),
        "confidence": conf,
        "notes": str(row.get("notes") or "").strip(),
    }


def dedupe(rows):
    out, seen = [], set()
    for raw in rows or []:
        l = normalize_label(raw)
        if not l["name"] or "-" not in l["name"]:
            continue
        key = (l["name"], l.get("fh", ""))
        if key not in seen:
            out.append(l); seen.add(key)
    return out


def rows_from_text(text: str):
    text = (text or "").replace("\r", "\n")
    labels = []
    for line in [x.strip() for x in text.split("\n") if x.strip()]:
        up = line.upper()
        names = NAME_RE.findall(up)
        fhs = FH_RE.findall(up)
        serials = SERIAL_RE.findall(up)
        macs = MAC_RE.findall(up)
        for i, n in enumerate(names):
            labels.append({
                "name": n,
                "fh": fhs[i] if i < len(fhs) else (fhs[0] if fhs else ""),
                "serial": serials[i] if i < len(serials) else (serials[0] if serials else ""),
                "mac": macs[i] if i < len(macs) else (macs[0] if macs else ""),
                "confidence": 0.7 if fhs else 0.55,
                "notes": "OCR/regex extraction"
            })
    if not labels:
        names = NAME_RE.findall(text.upper())
        fhs = FH_RE.findall(text.upper())
        for i, n in enumerate(names):
            labels.append({"name": n, "fh": fhs[i] if i < len(fhs) else "", "confidence": 0.55, "notes": "OCR/regex paired by order"})
    return dedupe(labels)


def extract_excel(content: bytes, filename: str):
    import pandas as pd
    labels = []
    if filename.lower().endswith(".csv"):
        sheets = {"csv": pd.read_csv(io.BytesIO(content), dtype=str).fillna("")}
    else:
        sheets = {k: v.fillna("") for k, v in pd.read_excel(io.BytesIO(content), sheet_name=None, dtype=str).items()}
    for _, df in sheets.items():
        cols = {str(c).strip().lower(): c for c in df.columns}
        for _, row in df.iterrows():
            loc = name = fh = serial = mac = ""
            for low, col in cols.items():
                val = str(row[col]).strip()
                if not val:
                    continue
                if any(x in low for x in ["location", "room", "or"]): loc = val
                if any(x in low for x in ["name", "neuron", "dropdown", "barcode"]): name = val
                if any(x in low for x in ["fh", "ecn", "asset", "current"]): fh = val
                if "serial" in low: serial = val
                if "mac" in low: mac = val
            if name:
                labels.append({"location": loc, "name": name, "fh": fh, "serial": serial, "mac": mac, "confidence": 0.99, "notes": "Excel column extraction"})
            else:
                labels.extend(rows_from_text(" ".join(str(v) for v in row.values)))
    return dedupe(labels)


def extract_pdf_text(content: bytes):
    text = ""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:
        try:
            import fitz
            doc = fitz.open(stream=content, filetype="pdf")
            text = "\n".join(page.get_text() for page in doc)
        except Exception:
            text = ""
    return text


def pdf_to_images(content: bytes, max_pages=4):
    images = []
    try:
        import fitz
        doc = fitz.open(stream=content, filetype="pdf")
        for page in doc[:max_pages]:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            images.append(("image/png", pix.tobytes("png")))
    except Exception:
        pass
    return images


def extract_image_ocr_text(content: bytes):
    try:
        from PIL import Image
        import pytesseract
        img = Image.open(io.BytesIO(content)).convert("L")
        return pytesseract.image_to_string(img, config="--psm 6")
    except Exception:
        return ""

AI_SYSTEM = """Extract barcode label rows from hospital equipment label sheets, photos, screenshots, PDFs, or tables.
Return ONLY valid JSON, no markdown.
Schema: {"labels":[{"location":"","name":"","fh":"","serial":"","mac":"","confidence":0.0,"notes":""}]}
Rules:
- name is the barcode/device name, e.g. RCH-PHOBOS, RCH-CARDIOLOGY-266, RMH-ZEUS, ERH-BIRCH.
- Ignore the Provation logo text and barcode bars.
- fh is the asset number, starts with FH followed by digits only, e.g. FH185499.
- Pair each FH number with the label in the same box/row/position. Do not invent FH numbers if not visible.
- Correct obvious OCR mistakes in numbers: O→0, I/l→1, G→6, B→8, S→5.
- serial often starts with WA. mac is 12 hex characters if visible.
- If uncertain, include best guess and confidence below 0.8 with notes.
"""


def ai_extract(content: bytes, filename: str, mime: str, text_hint: str, api_key: str, model: str):
    key = (api_key or "").strip() or os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return [], "No OpenAI API key found."
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        parts = [{"type": "input_text", "text": AI_SYSTEM + "\nOCR/text hint:\n" + (text_hint or "")[:12000]}]
        lower = filename.lower()
        image_items = []
        if lower.endswith(".pdf"):
            image_items = pdf_to_images(content, 4)
        elif lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")):
            image_items = [(mime or "image/png", content)]
        for imime, b in image_items[:4]:
            b64 = base64.b64encode(b).decode("ascii")
            parts.append({"type":"input_image", "image_url": f"data:{imime};base64,{b64}"})
        resp = client.responses.create(
            model=model or "gpt-4.1-mini",
            input=[{"role":"user", "content": parts}],
            temperature=0,
        )
        raw = (getattr(resp, "output_text", "") or "").strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.S)
        data = json.loads(raw)
        rows = dedupe(data.get("labels", []))
        for r in rows:
            if r.get("confidence") is None:
                r["confidence"] = 0.9
            r["notes"] = (r.get("notes") + " | AI extraction").strip(" |")
        return rows, ""
    except Exception as e:
        return [], str(e)


@app.post("/extract")
async def extract(file: UploadFile = File(...), use_ai: str = Form("true"), api_key: str = Form(""), model: str = Form("gpt-4.1-mini")):
    content = await file.read()
    fname = file.filename or "upload"
    lower = fname.lower()
    mime = file.content_type or "application/octet-stream"
    ocr_text = ""
    ocr_labels = []

    if lower.endswith((".xlsx", ".xls", ".csv")):
        ocr_labels = extract_excel(content, lower)
        try:
            import pandas as pd
            if lower.endswith(".csv"):
                ocr_text = pd.read_csv(io.BytesIO(content), dtype=str).fillna("").to_csv(index=False)
            else:
                sheets = pd.read_excel(io.BytesIO(content), sheet_name=None, dtype=str)
                ocr_text = "\n".join([f"SHEET {k}\n{v.fillna('').to_csv(index=False)}" for k, v in sheets.items()])
        except Exception:
            pass
    elif lower.endswith(".pdf"):
        ocr_text = extract_pdf_text(content)
        ocr_labels = rows_from_text(ocr_text)
    elif lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")):
        ocr_text = extract_image_ocr_text(content)
        ocr_labels = rows_from_text(ocr_text)
    else:
        raise HTTPException(400, "Unsupported file type. Upload Excel, CSV, PDF, or image.")

    ai_labels, ai_error = [], ""
    if use_ai.lower() == "true":
        ai_labels, ai_error = ai_extract(content, fname, mime, ocr_text, api_key, model)

    final = ai_labels if ai_labels else ocr_labels
    return {"labels": final, "ai_labels": ai_labels, "ocr_labels": ocr_labels, "ai_error": ai_error, "ocr_text_preview": ocr_text[:1500]}


@app.get("/ai-status")
def ai_status():
    return {"has_env_key": bool(os.getenv("OPENAI_API_KEY", "").strip()), "default_model": "gpt-4.1-mini"}


@app.get("/barcode.svg")
def barcode_svg(data: str = Query(..., min_length=1)):
    try:
        import barcode
        from barcode.writer import SVGWriter
        clean = clean_name(data)
        fp = io.BytesIO()
        code = barcode.get("code128", clean, writer=SVGWriter())
        code.write(fp, options={
            "module_width": 0.34,
            "module_height": 16.0,
            "quiet_zone": 3.5,
            "font_size": 0,
            "text_distance": 0,
            "write_text": False,
        })
        svg = fp.getvalue()
        return Response(content=svg, media_type="image/svg+xml", headers={"Cache-Control":"no-store"})
    except Exception as e:
        raise HTTPException(400, f"Could not generate barcode: {e}")


@app.post("/sample")
def sample():
    return {"labels": [
        {"location":"", "name":"RCH-PHOBOS", "fh":"FH185499", "serial":"", "mac":"", "confidence":0.99, "notes":"sample"},
        {"location":"", "name":"RCH-CARDIOLOGY-266", "fh":"FH163621", "serial":"", "mac":"", "confidence":0.99, "notes":"sample"},
        {"location":"", "name":"RCH-ENDO-01", "fh":"FH163774", "serial":"", "mac":"", "confidence":0.99, "notes":"sample"},
        {"location":"", "name":"RCH-ENDO-02", "fh":"FH163764", "serial":"", "mac":"", "confidence":0.99, "notes":"sample"},
        {"location":"", "name":"RCH-PACU-05", "fh":"FH163602", "serial":"", "mac":"", "confidence":0.99, "notes":"sample"},
        {"location":"", "name":"RCH-PACU-06", "fh":"FH163604", "serial":"", "mac":"", "confidence":0.99, "notes":"sample"},
        {"location":"", "name":"RCH-ELARA", "fh":"", "serial":"", "mac":"", "confidence":0.99, "notes":"sample"},
        {"location":"", "name":"RCH-LEDA", "fh":"FH205867", "serial":"WA24707936", "mac":"", "confidence":0.99, "notes":"sample"},
    ]}

app.mount("/assets", StaticFiles(directory=ASSET_DIR), name="assets")
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
