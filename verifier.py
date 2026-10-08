import re
import sys
import urllib.request
from pathlib import Path
from pypdf import PdfReader

BASE = Path(__file__).resolve().parent.parent
APP_URL = "http://127.0.0.1:5000/"


def expected_from_pdf(invoice_no):
    pdf = BASE / "data" / "invoices" / f"{invoice_no}.pdf"
    text = "\n".join(p.extract_text() or "" for p in PdfReader(str(pdf)).pages)
    vendor = re.search(r"INVOICE - (.+)", text).group(1).strip()
    amount = float(re.search(r"INR\s*([\d,]+\.?\d*)", text).group(1).replace(",", ""))
    y, m, d = re.search(r"Payment Due Date:\s*(\d{4})-(\d{2})-(\d{2})", text).groups()
    return {"vendor": vendor, "number": invoice_no, "amount": amount, "due": f"{d}/{m}/{y}"}


def fetch_rows():
    html = urllib.request.urlopen(APP_URL).read().decode("utf-8")
    rows = re.findall(r"<tr><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td></tr>", html)
    return [{"vendor": a, "number": b, "amount": c, "due": d} for a, b, c, d in rows]


def verify(invoice_no):
    exp = expected_from_pdf(invoice_no)
    found = [r for r in fetch_rows() if r["number"] == invoice_no]
    if not found:
        return False, f"FAIL: invoice {invoice_no} is not in the system."
    if len(found) > 1:
        return False, f"FAIL: invoice {invoice_no} appears {len(found)} times (duplicate)."
    row = found[0]
    problems = []
    if row["vendor"] != exp["vendor"]:
        problems.append(f"vendor {row['vendor']} != {exp['vendor']}")
    try:
        if abs(float(row["amount"]) - exp["amount"]) > 0.01:
            problems.append(f"amount {row['amount']} != {exp['amount']}")
    except ValueError:
        problems.append(f"amount '{row['amount']}' is not a number")
    if row["due"] != exp["due"]:
        problems.append(f"due date {row['due']} != {exp['due']}")
    if problems:
        return False, "FAIL: " + "; ".join(problems)
    return True, f"PASS: {invoice_no} is saved correctly ({row})"


if __name__ == "__main__":
    ok, msg = verify(sys.argv[1])
    print(msg)
    sys.exit(0 if ok else 1)