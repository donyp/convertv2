import json
import os
import re
import shutil
import sys
import uuid
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from converter.detector import detect_bank
from converter.excel_exporter import export_to_excel
from converter.parsers.bca import parse_bca_pdf
from converter.parsers.bsi import parse_bsi_pdf
from converter.parsers.muamalat import parse_muamalat_pdf
from converter.validator import validate_parse_result

PARSERS = {
    "BCA": parse_bca_pdf,
    "BSI": parse_bsi_pdf,
    "MUAMALAT": parse_muamalat_pdf,
}

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _safe_name(filename):
    return re.sub(r"[^\w.\- ]", "_", os.path.basename(filename or "")).strip() or "upload.pdf"


def _parse_multipart(body, content_type):
    match = re.search(r'boundary=(?:"([^"]+)"|([^;]+))', content_type)
    if not match:
        raise ValueError("Missing multipart boundary")
    boundary = (match.group(1) or match.group(2)).strip().encode()

    filename = None
    filedata = None
    fields = {}
    for chunk in body.split(b"--" + boundary):
        header_block, sep, content = chunk.partition(b"\r\n\r\n")
        if not sep:
            continue
        disposition = ""
        for line in header_block.split(b"\r\n"):
            if line.lower().startswith(b"content-disposition:"):
                disposition = line.decode("utf-8", "ignore")
                break
        name_m = re.search(r'name="([^"]*)"', disposition)
        file_m = re.search(r'filename="([^"]*)"', disposition)
        if content.endswith(b"\r\n"):
            content = content[:-2]
        if file_m:
            filename = file_m.group(1)
            filedata = content
        elif name_m:
            fields[name_m.group(1)] = content.decode("utf-8", "ignore")
    return filename, filedata, fields


class handler(BaseHTTPRequestHandler):
    def _json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._json(405, {"detail": "Gunakan POST dengan field 'file' (PDF) dan 'password' (opsional)."})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length)
            filename, filedata, fields = _parse_multipart(body, self.headers.get("Content-Type") or "")
            if not filedata:
                self._json(400, {"detail": "Field 'file' tidak ditemukan di request."})
                return

            password = fields.get("password") or None
            base = Path("/tmp") if os.path.exists("/tmp") else Path(".")
            job_dir = base / str(uuid.uuid4())
            job_dir.mkdir(parents=True, exist_ok=True)
            file_path = job_dir / _safe_name(filename)
            file_path.write_bytes(filedata)
            try:
                bank = detect_bank(str(file_path), password=password)
                result = PARSERS[bank](str(file_path), password=password)
                result = validate_parse_result(result)
                xlsx_path = file_path.with_suffix(".xlsx")
                export_to_excel(result, str(xlsx_path))
                data = xlsx_path.read_bytes()
            finally:
                shutil.rmtree(job_dir, ignore_errors=True)

            out_name = f"{bank}_{_safe_name(filename).rsplit('.', 1)[0]}.xlsx"
            self.send_response(200)
            self.send_header("Content-Type", XLSX_MIME)
            self.send_header("Content-Disposition", f'attachment; filename="{out_name}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as exc:
            self._json(500, {"detail": str(exc)})

    def log_message(self, fmt, *args):
        pass
