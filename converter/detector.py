import pdfplumber


def detect_bank(path: str, password: str = None) -> str:
    text = ""
    with pdfplumber.open(path, password=password) as pdf:
        for page in pdf.pages[:2]:
            text += "\n" + (page.extract_text() or "")
    upper = text.upper()
    score = {
        "BCA": 0,
        "BSI": 0,
        "MUAMALAT": 0,
    }
    if "REKENING GIRO" in upper or "KETERANGAN" in upper and "MUTASI" in upper:
        score["BCA"] += 3
    if "BCA" in upper:
        score["BCA"] += 1
    if "ACCOUNT STATEMENT" in upper and "FT NUMBER" in upper:
        score["BSI"] += 3
    if "BSI" in upper:
        score["BSI"] += 1
    if "ACCOUNT STATEMENT" in upper and "MUAMALAT" in upper:
        score["MUAMALAT"] += 3
    if "REFERENCE NUMBER" in upper and "EFFECTIVE" in upper:
        score["MUAMALAT"] += 2
    best = max(score, key=score.get)
    if score[best] == 0:
        raise ValueError("Bank tidak terdeteksi")
    return best
