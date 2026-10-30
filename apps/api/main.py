import shutil
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from converter.detector import detect_bank
from converter.excel_exporter import export_to_excel
from converter.parsers.bca import parse_bca_pdf
from converter.parsers.bsi import parse_bsi_pdf
from converter.parsers.muamalat import parse_muamalat_pdf
from converter.validator import validate_parse_result

BASE_DIR = Path(__file__).resolve().parents[2]
STORAGE_DIR = BASE_DIR / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

PARSERS = {
    "BCA": parse_bca_pdf,
    "BSI": parse_bsi_pdf,
    "MUAMALAT": parse_muamalat_pdf,
}

jobs: Dict[str, dict] = {}
jobs_lock = threading.Lock()

app = FastAPI(title="Bank Mutation Converter API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _set_job(job_id: str, **kwargs):
    with jobs_lock:
        jobs[job_id].update(kwargs)


def process_job(job_id: str, file_path: Path, password: Optional[str]):
    try:
        _set_job(job_id, status="processing", progress=10, message="Detecting bank")
        bank = detect_bank(str(file_path), password=password)
        _set_job(job_id, progress=25, message=f"Parsing {bank}")
        result = PARSERS[bank](str(file_path), password=password)
        _set_job(job_id, progress=60, message="Validating")
        result = validate_parse_result(result)
        xlsx_path = file_path.with_suffix(".xlsx")
        _set_job(job_id, progress=80, message="Exporting Excel")
        export_to_excel(result, str(xlsx_path))
        _set_job(
            job_id,
            status="completed",
            progress=100,
            message="Completed",
            bank=bank,
            result=result,
            xlsx_path=str(xlsx_path),
            completed_at=datetime.utcnow().isoformat(),
        )
    except Exception as exc:
        _set_job(job_id, status="failed", progress=100, message=str(exc))


@app.post("/api/v1/jobs")
async def create_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
):
    job_id = str(uuid.uuid4())
    job_dir = STORAGE_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    file_path = job_dir / file.filename
    with file_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    with jobs_lock:
        jobs[job_id] = {
            "id": job_id,
            "status": "queued",
            "progress": 0,
            "message": "Queued",
            "filename": file.filename,
            "created_at": datetime.utcnow().isoformat(),
            "bank": None,
            "result": None,
            "xlsx_path": None,
        }

    background_tasks.add_task(process_job, job_id, file_path, password)
    return {"job_id": job_id}


@app.get("/api/v1/jobs/{job_id}")
def get_job(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": job["id"],
        "status": job["status"],
        "progress": job["progress"],
        "message": job["message"],
        "filename": job["filename"],
        "bank": job["bank"],
        "validation_status": job["result"].validation_status if job["result"] else None,
        "transaction_count": len(job["result"].transactions) if job["result"] else None,
    }


@app.get("/api/v1/jobs/{job_id}/result")
def get_result(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "completed" or not job["result"]:
        raise HTTPException(status_code=409, detail="Result not ready")
    result = job["result"]
    return {
        "metadata": {
            "bank_code": result.metadata.bank_code,
            "bank_name": result.metadata.bank_name,
            "account_number": result.metadata.account_number,
            "account_name": result.metadata.account_name,
            "account_type": result.metadata.account_type,
            "currency": result.metadata.currency,
            "period_start": result.metadata.period_start.isoformat() if result.metadata.period_start else None,
            "period_end": result.metadata.period_end.isoformat() if result.metadata.period_end else None,
            "opening_balance": str(result.metadata.opening_balance) if result.metadata.opening_balance is not None else None,
            "closing_balance": str(result.metadata.closing_balance) if result.metadata.closing_balance is not None else None,
            "total_debit": str(result.metadata.total_debit) if result.metadata.total_debit is not None else None,
            "total_credit": str(result.metadata.total_credit) if result.metadata.total_credit is not None else None,
            "validation_status": result.validation_status,
            "validation_messages": result.validation_messages,
        },
        "transactions": [
            {
                "row_id": t.row_id,
                "page": t.page_number,
                "row": t.row_number,
                "transaction_date": t.transaction_date.isoformat() if t.transaction_date else None,
                "effective_date": t.effective_date.isoformat() if t.effective_date else None,
                "reference": t.reference_number,
                "description": t.description,
                "branch_or_ft": t.branch_or_ft,
                "debit": str(t.debit),
                "credit": str(t.credit),
                "balance": str(t.balance),
                "type": t.transaction_type,
                "flags": t.flags,
            }
            for t in result.transactions
        ],
    }


@app.get("/api/v1/jobs/{job_id}/download")
def download(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job or not job.get("xlsx_path"):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(job["xlsx_path"], filename=f"{job['bank']}_{job_id}.xlsx")


@app.delete("/api/v1/jobs/{job_id}")
def delete_job(job_id: str):
    with jobs_lock:
        job = jobs.pop(job_id, None)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job_dir = STORAGE_DIR / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir, ignore_errors=True)
    return {"deleted": True}


@app.get("/health")
def health():
    return {"status": "ok"}
