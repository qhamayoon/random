""Extract email metadata and bodies from .eml files, optionally using spaCy."""

from pathlib import Path
from email import policy
from email.parser import BytesParser
import pandas as pd

# Configuration
FOLDER = Path("emails")
OUTPUT = Path("extracted_emails.csv")
USE_SPACY = False  # Set True to extract people, organizations, and locations

# Optional: pip install spacy && python -m spacy download en_core_web_sm
if USE_SPACY:
    import spacy
    nlp = spacy.load("en_core_web_sm")

records = []

for file in FOLDER.rglob("*.eml"):
    try:
        with file.open("rb") as f:
            msg = BytesParser(policy=policy.default).parse(f)

        body = msg.get_body(preferencelist=("plain",))
        body_text = body.get_content() if body else ""

        record = {
            "From": str(msg.get("From", "")),
            "To": str(msg.get("To", "")),
            "CC": str(msg.get("Cc", "")),
            "Subject": str(msg.get("Subject", "")),
            "Timestamp": str(msg.get("Date", "")),
            "Body": body_text,
            "File": str(file),
        }

        if USE_SPACY:
            doc = nlp(body_text)
            for column, labels in {
                "People": {"PERSON"},
                "Organizations": {"ORG"},
                "Locations": {"GPE", "LOC"},
            }.items():
                record[column] = ", ".join(dict.fromkeys(
                    ent.text for ent in doc.ents if ent.label_ in labels
                ))

        records.append(record)
    except Exception as e:
        print(f"Error reading {file}: {e}")

columns = ["From", "To", "CC", "Subject", "Timestamp", "Body", "File"]
if USE_SPACY:
    columns += ["People", "Organizations", "Locations"]

df = pd.DataFrame(records, columns=columns)
df.to_csv(OUTPUT, index=False)
print(f"Extracted {len(df)} emails to {OUTPUT}")
