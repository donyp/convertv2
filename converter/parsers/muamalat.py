import re
from datetime import datetime
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


def parse_muamalat_pdf(path: str, password: str = None) -> ParseResult:
    metadata = StatementMetadata(bank_code="MUAMALAT", bank_name="Bank Muamalat")
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

                if "Reference" in text and "Transaction" in text and "Effective" in text:
                    in_table = True
                    continue
                if "ACCOUNT STATEMENT" in text or "All Rights Reserved" in text or re.match(r"^Page\s+\d+\s+of\s+\d+", text.strip()):
                    in_table = False
                    continue
                if not in_table:
                    if "Account No." in text:
                        m = re.search(r"Account No\.\s*:\s*(\S+)", text)
                        if m:
                            metadata.account_number = m.group(1)
                    elif "Account Type" in text:
                        m = re.search(r"Account Type\s*:\s*(.+)", text)
                        if m:
                            metadata.account_type = m.group(1).strip()
                    elif "Currency" in text:
                        m = re.search(r"Currency\s*:\s*(\S+)", text)
                        if m:
                            metadata.currency = m.group(1)
                    elif "Period" in text:
                        m = re.search(r"Period\s*:\s*(\S+)\s+to\s+(\S+)", text)
                        if m:
                            try:
                                metadata.period_start = datetime.strptime(m.group(1), "%d-%b-%Y").date()
                                metadata.period_end = datetime.strptime(m.group(2), "%d-%b-%Y").date()
                            except ValueError:
                                pass
                    elif "GARUDA" in text and "INDONESIA" in text and "ANKA" in text:
                        if not metadata.account_name:
                            metadata.account_name = text.split("JL")[0].strip() if "JL" in text else text.strip()
                    continue

                if not line_words:
                    continue

                first = line_words[0]
                # Starter row: first token in reference column and at least two dates in the line.
                date_tokens = [w for w in line_words if re.fullmatch(r"\d{2}-[A-Za-z]{3}-\d{4}", w["text"])]
                is_starter = first["x0"] < 140 and len(date_tokens) >= 2 and re.fullmatch(r"[0-9A-Za-z]{8,}", first["text"])

                if is_starter:
                    if current is not None:
                        _finalize_muamalat_transaction(current, transactions)
                    row_number += 1

                    current = {
                        "page_number": page_index,
                        "row_number": row_number,
                        "reference": first["text"],
                        "transaction_date": date_tokens[0]["text"] if len(date_tokens) > 0 else None,
                        "effective_date": date_tokens[1]["text"] if len(date_tokens) > 1 else None,
                        "debit": None,
                        "credit": None,
                        "balance": None,
                        "printed_balance": None,
                        "description_parts": [],
                        "raw_lines": [text],
                    }

                    for w in line_words:
                        x = w["x0"]
                        txt = w["text"]
                        if txt == first["text"] or txt in (current["transaction_date"], current["effective_date"]):
                            continue
                        if 315 <= x <= 395:
                            val = _to_decimal(txt)
                            if val is not None and current["debit"] is None:
                                current["debit"] = val
                        elif 420 <= x <= 480:
                            val = _to_decimal(txt)
                            if val is not None and current["credit"] is None:
                                current["credit"] = val
                        elif 530 <= x <= 705:
                            # Balance may be merged with account number/description.
                            m = re.match(r"^([\d,]+\.\d{2})(.*)$", txt)
                            if m and current["balance"] is None:
                                current["balance"] = _to_decimal(m.group(1))
                                current["printed_balance"] = current["balance"]
                                rest = m.group(2).strip()
                                if rest:
                                    current["description_parts"].append(rest)
                            # Separate description words on the same starter line.
                            if x >= 605 and txt not in (current["transaction_date"], current["effective_date"]):
                                # Avoid re-adding the merged balance token's trailing text twice.
                                if not (530 <= x <= 705 and re.match(r"^[\d,]+\.\d{2}", txt)):
                                    current["description_parts"].append(txt)
                else:
                    if current is None:
                        continue
                    current["raw_lines"].append(text)
                    if "Page" in text and "of" in text:
                        continue
                    # Continuation description lines: words on the right side.
                    for w in line_words:
                        x = w["x0"]
                        txt = w["text"]
                        if x >= 600:
                            current["description_parts"].append(txt)

        if current is not None:
            _finalize_muamalat_transaction(current, transactions)

    result = ParseResult(metadata=metadata, transactions=transactions, bank_confidence=0.96)
    return result


def _finalize_muamalat_transaction(current, transactions):
    debit = current["debit"] if current["debit"] is not None else Decimal("0")
    credit = current["credit"] if current["credit"] is not None else Decimal("0")
    if debit > 0 and credit == 0:
        txn_type = "debit"
    elif credit > 0 and debit == 0:
        txn_type = "credit"
    elif debit > 0 and credit > 0:
        txn_type = "debit"
    else:
        txn_type = "unknown"

    try:
        txn_date = datetime.strptime(current["transaction_date"], "%d-%b-%Y").date() if current["transaction_date"] else None
    except ValueError:
        txn_date = None
    try:
        eff_date = datetime.strptime(current["effective_date"], "%d-%b-%Y").date() if current["effective_date"] else None
    except ValueError:
        eff_date = None

    description = " ".join(current["description_parts"])
    description = re.sub(r"\s+", " ", description).strip()

    printed_balance = current["printed_balance"]
    balance = printed_balance if printed_balance is not None else Decimal("0")

    transaction = Transaction(
        row_id=f"MUAMALAT-{current['row_number']}",
        page_number=current["page_number"],
        row_number=current["row_number"],
        transaction_date=txn_date,
        effective_date=eff_date,
        reference_number=current["reference"],
        description=description,
        branch_or_ft="",
        debit=debit,
        credit=credit,
        balance=balance,
        printed_balance=printed_balance,
        transaction_type=txn_type,
        raw_text="\n".join(current["raw_lines"]),
    )
    transactions.append(transaction)
