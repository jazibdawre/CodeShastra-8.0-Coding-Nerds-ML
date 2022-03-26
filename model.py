import re
import spacy
import datefinder

nlp = spacy.load("en_core_web_sm")


def extract(text: str) -> dict:
    doc = nlp(text)

    url = re.search(r"(?P<url>https?://[^\s]+)", text)
    expiry = datefinder.find_dates(text)

    resp = {
        "link": "" if url is None else url.group("url"),
        "title": "",
        "discount": 0,
        "description": text,
        "expiry": "",
    }

    for ent in doc.ents:
        if ent.label_ == "PERCENT" and resp["discount"] == 0:
            resp["discount"] = int(ent.text[:-1])
        elif ent.label_ == "ORG" and resp["title"] == "":
            if len(ent.text) > 3:
                resp["title"] = ent.text
        elif ent.label_ == "DATE" and resp["expiry"] == "":
            resp["expiry"] = ent.text

    for dt in expiry:
        resp["expiry"] = dt

    return resp
