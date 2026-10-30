import os

from converter.parsers.bca import parse_bca_pdf
from converter.parsers.bsi import parse_bsi_pdf
from converter.parsers.muamalat import parse_muamalat_pdf
from converter.validator import validate_parse_result


BASE = os.path.dirname(os.path.dirname(__file__))


def test_bca():
    r = parse_bca_pdf(os.path.join(BASE, "BCA.pdf"))
    r = validate_parse_result(r)
    assert len(r.transactions) == 23
    assert r.metadata.account_number == "7510580138"
    assert r.validation_status == "PASS"


def test_bsi():
    r = parse_bsi_pdf(os.path.join(BASE, "BSI.pdf"))
    r = validate_parse_result(r)
    assert len(r.transactions) == 256
    assert r.metadata.account_number == "7143455356"
    assert r.validation_status in ("PASS", "WARNING")


def test_muamalat():
    r = parse_muamalat_pdf(os.path.join(BASE, "MUAMALAT.pdf"))
    r = validate_parse_result(r)
    assert len(r.transactions) == 807
    assert r.metadata.account_number == "3200024576"
    assert r.validation_status in ("PASS", "WARNING")
