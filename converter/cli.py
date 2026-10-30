import argparse
import json
from pathlib import Path

from converter.detector import detect_bank
from converter.parsers.bca import parse_bca_pdf
from converter.parsers.bsi import parse_bsi_pdf
from converter.parsers.muamalat import parse_muamalat_pdf
from converter.validator import validate_parse_result
from converter.excel_exporter import export_to_excel


PARSERS = {
    "BCA": parse_bca_pdf,
    "BSI": parse_bsi_pdf,
    "MUAMALAT": parse_muamalat_pdf,
}


def main():
    parser = argparse.ArgumentParser(description="Parse bank mutation PDF to Excel")
    parser.add_argument("pdf", help="Path to mutation PDF")
    parser.add_argument("--bank", choices=["BCA", "BSI", "MUAMALAT"], help="Bank code (auto-detect if omitted)")
    parser.add_argument("--json", help="Output JSON path")
    parser.add_argument("--xlsx", help="Output XLSX path")
    args = parser.parse_args()

    bank = args.bank or detect_bank(args.pdf)
    print("Detected bank:", bank)
    result = PARSERS[bank](args.pdf)
    result = validate_parse_result(result)

    print("Account:", result.metadata.account_number)
    print("Period:", result.metadata.period_start, "to", result.metadata.period_end)
    print("Transactions:", len(result.transactions))
    print("Validation:", result.validation_status)
    if result.validation_messages:
        for msg in result.validation_messages[:10]:
            print(" -", msg)

    if args.json:
        out = {
            "metadata": {
                "bank_code": result.metadata.bank_code,
                "account_number": result.metadata.account_number,
                "currency": result.metadata.currency,
                "period_start": result.metadata.period_start.isoformat() if result.metadata.period_start else None,
                "period_end": result.metadata.period_end.isoformat() if result.metadata.period_end else None,
                "opening_balance": str(result.metadata.opening_balance) if result.metadata.opening_balance is not None else None,
                "closing_balance": str(result.metadata.closing_balance) if result.metadata.closing_balance is not None else None,
                "total_debit": str(result.metadata.total_debit) if result.metadata.total_debit is not None else None,
                "total_credit": str(result.metadata.total_credit) if result.metadata.total_credit is not None else None,
                "validation_status": result.validation_status,
            },
            "transactions": [
                {
                    "row_id": t.row_id,
                    "page": t.page_number,
                    "row": t.row_number,
                    "date": t.transaction_date.isoformat() if t.transaction_date else None,
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
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        print("JSON written to", args.json)

    if args.xlsx:
        path = args.xlsx
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        export_to_excel(result, path)
        print("XLSX written to", path)


if __name__ == "__main__":
    main()
