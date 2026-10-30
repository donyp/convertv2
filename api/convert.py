import os
import shutil
import sys
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

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

app = FastAPI()


@app.post("/")
@app.post("/api/convert")
@app.post("/api/v1/convert")
async def convert(file: UploadFile = File(...), password: str = Form(None)):
    base = Path("/tmp") if os.path.exists("/tmp") else Path(".")
    job_dir = base / str(uuid.uuid4())
    job_dir.mkdir(parents=True, exist_ok=True)
    file_path = job_dir / (file.filename or "upload.pdf")
    with file_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        bank = detect_bank(str(file_path), password=password)
        result = PARSERS[bank](str(file_path), password=password)
        result = validate_parse_result(result)
        xlsx_path = file_path.with_suffix(".xlsx")
        export_to_excel(result, str(xlsx_path))
        with xlsx_path.open("rb") as f:
            data = f.read()
        try:
            file_path.unlink(missing_ok=True)
            xlsx_path.unlink(missing_ok=True)
            job_dir.rmdir()
        except Exception:
            pass
        filename = f"{bank}_{file.filename or 'mutation'}.xlsx"
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as exc:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(exc))
