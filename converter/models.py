from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import List, Optional


@dataclass
class Transaction:
    row_id: str
    page_number: int
    row_number: int
    transaction_date: Optional[date]
    effective_date: Optional[date]
    reference_number: str
    description: str
    branch_or_ft: str
    debit: Decimal
    credit: Decimal
    balance: Decimal
    transaction_type: str
    printed_balance: Optional[Decimal] = None
    confidence: float = 1.0
    flags: List[str] = field(default_factory=list)
    raw_text: str = ""


@dataclass
class StatementMetadata:
    bank_code: str
    bank_name: str
    account_number: str = ""
    account_name: str = ""
    account_type: str = ""
    currency: str = "IDR"
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    branch: str = ""
    opening_balance: Optional[Decimal] = None
    closing_balance: Optional[Decimal] = None
    total_debit: Optional[Decimal] = None
    total_credit: Optional[Decimal] = None
    debit_record_count: Optional[int] = None
    credit_record_count: Optional[int] = None


@dataclass
class ParseResult:
    metadata: StatementMetadata
    transactions: List[Transaction] = field(default_factory=list)
    bank_confidence: float = 0.0
    validation_status: str = "NOT_RUN"
    validation_messages: List[str] = field(default_factory=list)