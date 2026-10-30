import os
import shutil
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

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

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "mutation-files")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        from supabase import create_client

        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        supabase = None

# In-memory fallback for local development.
jobs: Dict[str, dict] = {}
jobs_lock = threading.Lock()

app = FastAPI(title="Bank Mutation Converter API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _serialize_result(result) -> Dict[str, Any]:
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


def _create_job(job_id: str, filename: str):
    payload = {
        "id": job_id,
        "status": "queued",
        "progress": 0,
        "message": "Queued",
        "filename": filename,
        "bank": None,
        "validation_status": None,
        "transaction_count": None,
        "result_json": None,
        "xlsx_bytes": None,
        "created_at": datetime.utcnow().isoformat(),
        "completed_at": None,
    }
    if supabase:
        supabase.table("jobs").insert(payload).execute()
    else:
        with jobs_lock:
            jobs[job_id] = payload.copy()


def _update_job(job_id: str, **kwargs):
    if supabase:
        supabase.table("jobs").update(kwargs).eq("id", job_id).execute()
    else:
        with jobs_lock:
            if job_id in jobs:
                jobs[job_id].update(kwargs)


def _get_job(job_id: str) -> Optional[dict]:
    if supabase:
        res = supabase.table("jobs").select("*").eq("id", job_id).execute()
        if res.data:
            return res.data[0]
        return None
    with jobs_lock:
        return jobs.get(job_id)


def _delete_job(job_id: str) -> bool:
    job = _get_job(job_id)
    if not job:
        return False
    if supabase:
        supabase.table("jobs").delete().eq("id", job_id).execute()
    else:
        with jobs_lock:
            jobs.pop(job_id, None)
        job_dir = STORAGE_DIR / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
    return True


def _upload_storage(job_id: str, local_path: Path, remote_name: str) -> Optional[str]:
    if not supabase:
        return str(local_path)
    remote_path = f"{job_id}/{remote_name}"
    with local_path.open("rb") as f:
        supabase.storage.from_(SUPABASE_BUCKET).upload(
            remote_path,
            f,
            file_options={"content-type": "application/octet-stream", "upsert": "true"},
        )
    return remote_path


def _signed_url(path: str) -> str:
    if not supabase:
        return path
    res = supabase.storage.from_(SUPABASE_BUCKET).create_signed_url(path, 3600)
    return res.get("signedURL") or res.get("signedUrl") or path


def process_job(job_id: str, file_path: Path, password: Optional[str]):
    try:
        _update_job(job_id, status="processing", progress=10, message="Detecting bank")
        bank = detect_bank(str(file_path), password=password)
        _update_job(job_id, progress=25, message=f"Parsing {bank}")
        result = PARSERS[bank](str(file_path), password=password)
        _update_job(job_id, progress=60, message="Validating")
        result = validate_parse_result(result)
        xlsx_local = file_path.with_suffix(".xlsx")
        _update_job(job_id, progress=80, message="Exporting Excel")
        export_to_excel(result, str(xlsx_local))

        # Read bytes into memory, then remove all temp files (no persistent storage).
        with xlsx_local.open("rb") as f:
            xlsx_bytes = f.read()
        import base64

        xlsx_b64 = base64.b64encode(xlsx_bytes).decode("ascii")

        # Clean temp files.
        try:
            file_path.unlink(missing_ok=True)
            xlsx_local.unlink(missing_ok=True)
            file_path.parent.rmdir()
        except Exception:
            pass

        result_json = _serialize_result(result)
        _update_job(
            job_id,
            status="completed",
            progress=100,
            message="Completed",
            bank=bank,
            validation_status=result.validation_status,
            transaction_count=len(result.transactions),
            result_json=result_json,
            xlsx_bytes=xlsx_b64,
            completed_at=datetime.utcnow().isoformat(),
        )
    except Exception as exc:
        _update_job(job_id, status="failed", progress=100, message=str(exc))


@app.post("/api/v1/jobs")
async def create_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
):
    job_id = str(uuid.uuid4())
    job_dir = STORAGE_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    file_path = job_dir / (file.filename or "upload.pdf")
    with file_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    _create_job(job_id, file.filename or "upload.pdf")
    background_tasks.add_task(process_job, job_id, file_path, password)
    return {"job_id": job_id}


@app.get("/api/v1/jobs/{job_id}")
def get_job(job_id: str):
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": job["id"],
        "status": job["status"],
        "progress": job["progress"],
        "message": job["message"],
        "filename": job["filename"],
        "bank": job["bank"],
        "validation_status": job["validation_status"],
        "transaction_count": job["transaction_count"],
    }


@app.get("/api/v1/jobs/{job_id}/result")
def get_result(job_id: str):
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "completed" or not job.get("result_json"):
        raise HTTPException(status_code=409, detail="Result not ready")
    return job["result_json"]


@app.get("/api/v1/jobs/{job_id}/download")
def download(job_id: str):
    job = _get_job(job_id)
    if not job or not job.get("xlsx_bytes"):
        raise HTTPException(status_code=404, detail="File not found")
    import base64

    from fastapi.responses import Response

    data = base64.b64decode(job["xlsx_bytes"])
    filename = f"{job.get('bank') or 'mutation'}_{job_id}.xlsx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.delete("/api/v1/jobs/{job_id}")
def delete_job(job_id: str):
    ok = _delete_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"deleted": True}


@app.get("/health")
def health():
    return {"status": "ok", "supabase": bool(supabase)}
