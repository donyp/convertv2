import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional

import pdfplumber

from converter.models import ParseResult, StatementMetadata, Transaction


def _to_decimal(value: str) -> Optional[Decimal]:
    if not value:
        return None
    value = value.replace(" ", "")
    if "," in value and "." in value:
        value = value.replace(",", "")
    elif "," in value and "." not in value:
        parts = value.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            value = parts[0] + "." + parts[1]
        else:
            value = value.replace(",", "")
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def parse_bsi_pdf(path: str, password: str = None) -> ParseResult:
    metadata = StatementMetadata(bank_code="BSI", bank_name="BSI")
    transactions: List[Transaction] = []
    current: Optional[Dict] = None
    row_number = 0

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

                if "Date" in text and "FT Number" in text and "Description" in text:
                    in_table = True
                    continue
                if "Account Statement" in text or re.match(r"^Page\s+\d+/\d+", text.strip()):
                    in_table = False
                    continue
                if not in_table:
                    if "Account" in text and ":" in text and "IDR" not in text.split(":")[-1]:
                        m = re.search(r"Account\s*:\s*(\S+)", text)
                        if m and not metadata.account_number:
                            metadata.account_number = m.group(1)
                    elif text.startswith("Date"):
                        m = re.search(r"Date\s*:\s*(.+)", text)
                        if m and " - " in m.group(1):
                            parts = m.group(1).split(" - ")
                            try:
                                metadata.period_start = datetime.strptime(parts[0].strip(), "%d %b %Y").date()
                                metadata.period_end = datetime.strptime(parts[1].strip(), "%d %b %Y").date()
                            except ValueError:
                                pass
                    elif text.startswith("Opening Balance"):
                        m = re.search(r"Opening Balance\s*:\s*IDR\s*([\d,\.]+)", text)
                        if m:
                            metadata.opening_balance = _to_decimal(m.group(1))
                    elif text.startswith("Closing Balance"):
                        m = re.search(r"Closing Balance\s*:\s*IDR\s*([\d,\.]+)", text)
                        if m:
                            metadata.closing_balance = _to_decimal(m.group(1))
                    elif text.startswith("Total Debit Amount"):
                        m = re.search(r"Total Debit Amount\s*:\s*IDR\s*([\d,\.]+)", text)
                        if m:
                            metadata.total_debit = _to_decimal(m.group(1))
                    elif text.startswith("Total Debit Record"):
                        m = re.search(r"Total Debit Record\s*:\s*(\d+)", text)
                        if m:
                            metadata.debit_record_count = int(m.group(1))
                    elif text.startswith("Total Credit Amount"):
                        m = re.search(r"Total Credit Amount\s*:\s*IDR\s*([\d,\.]+)", text)
                        if m:
                            metadata.total_credit = _to_decimal(m.group(1))
                    elif text.startswith("Total Credit Record"):
                        m = re.search(r"Total Credit Record\s*:\s*(\d+)", text)
                        if m:
                            metadata.credit_record_count = int(m.group(1))
                    elif text.startswith("Branch"):
                        m = re.search(r"Branch\s*:\s*(\S+)", text)
                        if m:
                            metadata.branch = m.group(1)
                    elif "GARUDA" in text and "/" in text:
                        # Account name line, e.g. PT GARUDA GEMILANG INDONESIA / IDR
                        name = text.split("/")[0].strip()
                        if name and not metadata.account_name:
                            metadata.account_name = name
                    continue

                if not line_words:
                    continue

                first = line_words[0]
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", first["text"]):
                    if current is not None:
                        _finalize_bsi_transaction(current, transactions)
                    row_number += 1
                    # Parse date and FT number from second token.
                    ft_token = line_words[1]["text"] if len(line_words) > 1 else ""
                    time_part = ""
                    ft_number = ft_token
                    m = re.match(r"^(\d{2}:\d{2}:\d{2})(.+)$", ft_token)
                    if m:
                        time_part = m.group(1)
                        ft_number = m.group(2)

                    current = {
                        "page_number": page_index,
                        "row_number": row_number,
                        "date_token": first["text"],
                        "time_part": time_part,
                        "ft_number": ft_number,
                        "description_parts": [],
                        "currency": "",
                        "amount": None,
                        "is_debit": False,
                        "is_credit": False,
                        "balance": None,
                        "raw_lines": [text],
                    }

                    for w in line_words:
                        txt = w["text"]
                        x = w["x0"]
                        if txt == first["text"] or (len(line_words) > 1 and txt == line_words[1]["text"]):
                            continue
                        if 390 <= x <= 415:
                            current["currency"] = txt
                        elif 425 <= x <= 480:
                            clean = txt
                            if clean.endswith("DB") or clean.endswith("CR"):
                                clean = clean[:-2]
                            val = _to_decimal(clean)
                            if val is not None and current["amount"] is None:
                                current["amount"] = val
                            if "DB" in txt:
                                current["is_debit"] = True
                            elif "CR" in txt:
                                current["is_credit"] = True
                        elif 470 <= x <= 510:
                            if txt == "DB":
                                current["is_debit"] = True
                            elif txt == "CR":
                                current["is_credit"] = True
                        elif 505 <= x <= 565:
                            val = _to_decimal(txt)
                            if val is not None and current["balance"] is None:
                                current["balance"] = val
                        else:
                            current["description_parts"].append(txt)
                else:
                    if current is None:
                        continue
                    current["raw_lines"].append(text)
                    # Skip obvious footer/header continuation.
                    if "Account Statement" in text or "Page" in text:
                        continue
                    for w in line_words:
                        x = w["x0"]
                        txt = w["text"]
                        if x >= 165:
                            current["description_parts"].append(txt)

        if current is not None:
            _finalize_bsi_transaction(current, transactions)

    # Post-process running balances where printed balance missing? BSI always prints balance.
    result = ParseResult(metadata=metadata, transactions=transactions, bank_confidence=0.97)
    return result


def _finalize_bsi_transaction(current, transactions):
    amount = current["amount"] if current["amount"] is not None else Decimal("0")
    if current["is_debit"]:
        debit = amount
        credit = Decimal("0")
        txn_type = "debit"
    elif current["is_credit"]:
        debit = Decimal("0")
        credit = amount
        txn_type = "credit"
    else:
        # Fallback: unknown marker, treat as debit.
        debit = amount
        credit = Decimal("0")
        txn_type = "debit"

    try:
        txn_date = datetime.strptime(current["date_token"], "%Y-%m-%d").date()
    except ValueError:
        txn_date = None

    description = " ".join(current["description_parts"])
    description = re.sub(r"\s+", " ", description).strip()

    printed_balance = current["balance"]
    balance = printed_balance if printed_balance is not None else Decimal("0")

    transaction = Transaction(
        row_id=f"BSI-{current['row_number']}",
        page_number=current["page_number"],
        row_number=current["row_number"],
        transaction_date=txn_date,
        effective_date=None,
        reference_number=current["ft_number"],
        description=description,
        branch_or_ft=current["ft_number"],
        debit=debit,
        credit=credit,
        balance=balance,
        printed_balance=printed_balance,
        transaction_type=txn_type,
        raw_text="\n".join(current["raw_lines"]),
    )
    transactions.append(transaction)
