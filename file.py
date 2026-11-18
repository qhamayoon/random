"""
Extract emails from PDFs: from, to, email address, timestamp, content, signature.

Setup:
    pip install pandas pdfplumber spacy
    python -m spacy download en_core_web_sm

Usage:
    python email_extractor.py path/to/pdf_folder output.csv
"""
import re
import sys
from pathlib import Path

import pandas as pd
import pdfplumber
import spacy

nlp = spacy.load("en_core_web_sm")

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
HEADER_RE = {
    "from": re.compile(r"^From:\s*(.+)$", re.I | re.M),
    "to": re.compile(r"^To:\s*(.+)$", re.I | re.M),
    "timestamp": re.compile(r"^(?:Date|Sent):\s*(.+)$", re.I | re.M),
}
SIGNOFF_RE = re.compile(
    r"^\s*(--|best|regards|best regards|kind regards|thanks|thank you|sincerely|cheers)\b.*$",
    re.I | re.M,
)


def read_pdf(path):
    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def split_emails(text):
    # Each email starts at a "From:" line
    parts = re.split(r"(?=^From:)", text, flags=re.M)
    return [p.strip() for p in parts if p.strip().lower().startswith("from:")]


def get_header(name, email_text):
    match = HEADER_RE[name].search(email_text)
    return match.group(1).strip() if match else ""


def split_body_and_signature(body):
    match = SIGNOFF_RE.search(body)
    if match:
        return body[: match.start()].strip(), body[match.start():].strip()
    # Fallback: treat the last 4 lines as the signature if spaCy finds a name there
    lines = body.splitlines()
    tail = "\n".join(lines[-4:])
    if any(ent.label_ == "PERSON" for ent in nlp(tail).ents):
        return "\n".join(lines[:-4]).strip(), tail.strip()
    return body.strip(), ""


def parse_email(email_text, source):
    sender = get_header("from", email_text)
    address = EMAIL_RE.search(sender)

    # Body starts after the last header line (blank line or Subject line)
    header_end = max(
        (m.end() for m in re.finditer(r"^(From|To|Cc|Date|Sent|Subject):.*$", email_text, re.I | re.M)),
        default=0,
    )
    content, signature = split_body_and_signature(email_text[header_end:])

    # Use spaCy to get the sender's name if the From line only has an address
    sender_name = EMAIL_RE.sub("", sender).strip(" <>\"")
    if not sender_name and signature:
        people = [e.text for e in nlp(signature).ents if e.label_ == "PERSON"]
        sender_name = people[0] if people else ""

    return {
        "source_file": source,
        "from": sender_name,
        "to": get_header("to", email_text),
        "email_address": address.group(0) if address else "",
        "timestamp": get_header("timestamp", email_text),
        "content": content,
        "signature": signature,
    }


def main(folder, output):
    rows = []
    for pdf_path in sorted(Path(folder).glob("*.pdf")):
        text = read_pdf(pdf_path)
        for email_text in split_emails(text):
            rows.append(parse_email(email_text, pdf_path.name))
        print(f"{pdf_path.name}: processed")

    df = pd.DataFrame(rows)
    df.to_csv(output, index=False)
    print(f"Saved {len(df)} emails to {output}")


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "emails"
    output = sys.argv[2] if len(sys.argv) > 2 else "emails.csv"
    main(folder, output)
