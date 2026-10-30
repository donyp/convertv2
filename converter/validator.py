from decimal import Decimal

from converter.models import ParseResult


def validate_parse_result(result: ParseResult) -> ParseResult:
    messages = []
    status = "PASS"
    transactions = result.transactions
    metadata = result.metadata

    # Running balance validation.
    running = metadata.opening_balance if metadata.opening_balance is not None else None
    for txn in transactions:
        if running is None:
            running = txn.balance
            continue
        expected = running + txn.credit - txn.debit
        if abs(expected - txn.balance) > Decimal("0.01"):
            messages.append(f"Row {txn.row_number}: saldo berjalan tidak cocok (expected {expected}, actual {txn.balance})")
            status = "FAIL"
        running = txn.balance

    # Closing balance.
    if metadata.closing_balance is not None and transactions:
        if abs(transactions[-1].balance - metadata.closing_balance) > Decimal("0.01"):
            messages.append(f"Saldo akhir tidak cocok (expected {metadata.closing_balance}, actual {transactions[-1].balance})")
            status = "FAIL"

    # Total debit.
    if metadata.total_debit is not None:
        actual_debit = sum((t.debit for t in transactions), Decimal("0"))
        if abs(actual_debit - metadata.total_debit) > Decimal("0.01"):
            messages.append(f"Total debit tidak cocok (expected {metadata.total_debit}, actual {actual_debit})")
            status = "FAIL"

    # Total credit.
    if metadata.total_credit is not None:
        actual_credit = sum((t.credit for t in transactions), Decimal("0"))
        if abs(actual_credit - metadata.total_credit) > Decimal("0.01"):
            messages.append(f"Total kredit tidak cocok (expected {metadata.total_credit}, actual {actual_credit})")
            status = "FAIL"

    # Record counts.
    if metadata.debit_record_count is not None:
        actual_count = sum(1 for t in transactions if t.transaction_type == "debit")
        if actual_count != metadata.debit_record_count:
            messages.append(f"Jumlah debit tidak cocok (expected {metadata.debit_record_count}, actual {actual_count})")
            status = "WARNING"
    if metadata.credit_record_count is not None:
        actual_count = sum(1 for t in transactions if t.transaction_type == "credit")
        if actual_count != metadata.credit_record_count:
            messages.append(f"Jumlah kredit tidak cocok (expected {metadata.credit_record_count}, actual {actual_count})")
            status = "WARNING"

    # Duplicate references (warning only).
    refs = [t.reference_number for t in transactions if t.reference_number]
    seen = set()
    duplicates = set()
    for ref in refs:
        if ref in seen:
            duplicates.add(ref)
        seen.add(ref)
    if duplicates:
        messages.append(f"Referensi duplikat: {', '.join(sorted(duplicates)[:10])}")
        if status == "PASS":
            status = "WARNING"

    result.validation_status = status
    result.validation_messages = messages
    return result
