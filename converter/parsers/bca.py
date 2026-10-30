import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional

import pdfplumber

from converter.models import ParseResult, StatementMetadata, Transaction

MONTHS = {
    "JANUARI": 1, "FEBRUARI": 2, "MARET": 3, "APRIL": 4, "MEI": 5, "JUNI": 6,
    "JULI": 7, "AGUSTUS": 8, "SEPTEMBER": 9, "OKTOBER": 10, "NOVEMBER": 11, "DESEMBER": 12,
    "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4, "MAY": 5, "JUNE": 6,
    "JULY": 7, "AUGUST": 8, "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12,
}


def _to_decimal(value: str) -> Optional[Decimal]:
    if not value:
        return None
    value = value.replace(" ", "")
    # BCA uses comma as thousands separator and dot as decimal separator.
    if "," in value and "." in value:
        value = value.replace(",", "")
    elif "," in value and "." not in value:
        # Assume comma is decimal separator only if one comma and 1-2 digits after it.
        parts = value.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            value = parts[0] + "." + parts[1]
        else:
            value = value.replace(",", "")
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


def _is_date_token(token: str) -> bool:
    return bool(re.fullmatch(r"\d{2}/\d{2}", token))


def _parse_period(period_text: str):
    parts = period_text.upper().split()
    if len(parts) >= 2 and parts[0] in MONTHS:
        return MONTHS[parts[0]], int(parts[1])
    return None, None


def parse_bca_pdf(path: str, password: str = None) -> ParseResult:
    metadata = StatementMetadata(bank_code="BCA", bank_name="BCA")
    transactions: List[Transaction] = []
    current: Optional[Dict] = None
    row_number = 0
    period_month = None
    period_year = None

    with pdfplumber.open(path, password=password) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            words = page.extract_words()
            lines: Dict[int, List[Dict]] = {}
            for word in words:
                lines.setdefault(round(word["top"]), []).append(word)

            in_table = False
            for top in sorted(lines):
                line_words = sorted(lines[top], key=lambda w: w["x0"])
                text = " ".join(w["text"] for w in line_words)

                if text.startswith("SALDO AWAL"):
                    m = re.search(r"SALDO AWAL\s*:\s*([\d,\.]+)", text)
                    if m:
                        metadata.opening_balance = _to_decimal(m.group(1))
                    continue
                if text.startswith("MUTASI CR"):
                    m = re.search(r"MUTASI CR\s*:\s*([\d,\.]+)", text)
                    if m:
                        metadata.total_credit = _to_decimal(m.group(1))
                    continue
                if text.startswith("MUTASI DB"):
                    m = re.search(r"MUTASI DB\s*:\s*([\d,\.]+)", text)
                    if m:
                        metadata.total_debit = _to_decimal(m.group(1))
                    continue
                if text.startswith("SALDO AKHIR"):
                    m = re.search(r"SALDO AKHIR\s*:\s*([\d,\.]+)", text)
                    if m:
                        metadata.closing_balance = _to_decimal(m.group(1))
                    continue

                if "TANGGAL" in text and "KETERANGAN" in text:
                    in_table = True
                    continue
                if "Bersambung ke Halaman" in text or re.match(r"^\d+\s*/\s*\d+$", text.strip()):
                    in_table = False
                    continue
                if not in_table:
                    # Metadata and summary may appear outside table.
                    if "NO. REKENING" in text:
                        m = re.search(r"NO\.\s*REKENING\s*:\s*(\S+)", text)
                        if m:
                            metadata.account_number = m.group(1)
                    elif "PERIODE" in text:
                        m = re.search(r"PERIODE\s*:\s*(.+)", text)
                        if m:
                            period_month, period_year = _parse_period(m.group(1).strip())
                            if period_month and period_year:
                                import calendar
                                metadata.period_start = date(period_year, period_month, 1)
                                last_day = calendar.monthrange(period_year, period_month)[1]
                                metadata.period_end = date(period_year, period_month, last_day)
                    elif "MATA UANG" in text:
                        m = re.search(r"MATA UANG\s*:\s*(\S+)", text)
                        if m:
                            metadata.currency = m.group(1)
                    elif text.startswith("SALDO AWAL"):
                        m = re.search(r"SALDO AWAL\s*:?\s*([\d,\.]+)", text)
                        if m:
                            metadata.opening_balance = _to_decimal(m.group(1))
                    elif text.startswith("MUTASI CR"):
                        m = re.search(r"MUTASI CR\s*:?\s*([\d,\.]+)", text)
                        if m:
                            metadata.total_credit = _to_decimal(m.group(1))
                    elif text.startswith("MUTASI DB"):
                        m = re.search(r"MUTASI DB\s*:?\s*([\d,\.]+)", text)
                        if m:
                            metadata.total_debit = _to_decimal(m.group(1))
                    elif text.startswith("SALDO AKHIR"):
                        m = re.search(r"SALDO AKHIR\s*:?\s*([\d,\.]+)", text)
                        if m:
                            metadata.closing_balance = _to_decimal(m.group(1))
                    continue

                if not line_words:
                    continue

                first = line_words[0]
                if _is_date_token(first["text"]):
                    # Finalize previous transaction.
                    if current is not None:
                        _finalize_bca_transaction(current, transactions, metadata, period_month, period_year)
                    if "SALDO AWAL" in text:
                        for w in line_words:
                            if 485 <= w["x0"] <= 585:
                                val = _to_decimal(w["text"])
                                if val is not None:
                                    metadata.opening_balance = val
                        current = None
                        continue
                    row_number += 1
                    current = {
                        "page_number": page_index,
                        "row_number": row_number,
                        "date_token": first["text"],
                        "cbg": "",
                        "amount": None,
                        "has_db": False,
                        "balance": None,
                        "description_parts": [],
                        "raw_lines": [text],
                    }
                    # Parse fields from the starter line.
                    for w in line_words:
                        txt = w["text"]
                        x = w["x0"]
                        if txt == first["text"]:
                            continue
                        if 285 <= x <= 345 and re.fullmatch(r"\d{4}", txt):
                            current["cbg"] = txt
                        elif 355 <= x <= 450:
                            if txt == "DB":
                                current["has_db"] = True
                            else:
                                val = _to_decimal(txt)
                                if val is not None and current["amount"] is None:
                                    current["amount"] = val
                        elif 485 <= x <= 585:
                            val = _to_decimal(txt)
                            if val is not None and current["balance"] is None:
                                current["balance"] = val
                        else:
                            # Description tokens.
                            if not (285 <= x <= 345 and re.fullmatch(r"\d{4}", txt)):
                                current["description_parts"].append(txt)
                else:
                    if current is None:
                        continue
                    current["raw_lines"].append(text)
                    # Continuation description lines.
                    for w in line_words:
                        x = w["x0"]
                        txt = w["text"]
                        # Skip tokens that are clearly amount/balance/cbg on continuation lines.
                        if 355 <= x <= 450 and _to_decimal(txt) is not None:
                            if current["amount"] is None:
                                current["amount"] = _to_decimal(txt)
                            continue
                        if 485 <= x <= 585 and _to_decimal(txt) is not None:
                            if current["balance"] is None:
                                current["balance"] = _to_decimal(txt)
                            continue
                        val = _to_decimal(txt)
                        if val is not None and current.get("amount") is not None and val == current["amount"]:
                            continue
                        current["description_parts"].append(txt)

        if current is not None:
            _finalize_bca_transaction(current, transactions, metadata, period_month, period_year)

    # Sort by row number (already in order).
    running = metadata.opening_balance if metadata.opening_balance is not None else Decimal("0")
    for txn in transactions:
        running = running + txn.credit - txn.debit
        if txn.printed_balance is not None:
            if running != txn.printed_balance:
                txn.flags.append("balance_mismatch")
            txn.balance = txn.printed_balance
            running = txn.printed_balance
        else:
            txn.balance = running

    result = ParseResult(metadata=metadata, transactions=transactions, bank_confidence=0.98)
    return result


def _finalize_bca_transaction(current, transactions, metadata, period_month, period_year):
    amount = current["amount"] if current["amount"] is not None else Decimal("0")
    printed_balance = current["balance"]
    balance = printed_balance if printed_balance is not None else Decimal("0")
    is_debit = current["has_db"] or (amount > 0 and current["balance"] is not None)
    # BCA marks debit with DB. Rows without DB are treated as credit.
    if current["has_db"]:
        debit = amount
        credit = Decimal("0")
        txn_type = "debit"
    else:
        debit = Decimal("0")
        credit = amount
        txn_type = "credit"

    # Convert DD/MM to full date using statement period.
    day, month = current["date_token"].split("/")
    day_i = int(day)
    month_i = int(month)
    if period_year is not None:
        year = period_year
    else:
        year = date.today().year
    # If transaction month does not match period month, still use period year.
    try:
        txn_date = date(year, month_i, day_i)
    except ValueError:
        txn_date = None

    description = " ".join(current["description_parts"])
    description = re.sub(r"\s+", " ", description).strip()

    transaction = Transaction(
        row_id=f"BCA-{current['row_number']}",
        page_number=current["page_number"],
        row_number=current["row_number"],
        transaction_date=txn_date,
        effective_date=None,
        reference_number="",
        description=description,
        branch_or_ft=current["cbg"],
        debit=debit,
        credit=credit,
        balance=balance,
        printed_balance=printed_balance,
        transaction_type=txn_type,
        raw_text="\n".join(current["raw_lines"]),
    )
    transactions.append(transaction)
