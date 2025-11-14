import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dateutil import parser as dateparser
import uuid

BASE_URL = "https://www.flsh.uha.fr/"

def fetch_events():
    html = requests.get(BASE_URL, timeout=10)
    html.raise_for_status()
    soup = BeautifulSoup(html.text, "html.parser")

    # 1. Trouver le titre "L'AGENDA DE LA FACULTÉ"
    agenda_title = soup.find(
        lambda tag: tag.name in ["h2", "h3"]
        and "AGENDA DE LA FACULTÉ" in tag.get_text()
    )
    if not agenda_title:
        raise RuntimeError("Impossible de trouver la rubrique 'L'AGENDA DE LA FACULTÉ'")

    events = []
    cursor = agenda_title
    # On avance dans le DOM jusqu'à ce qu'on sorte de la zone agenda
    while cursor:
        cursor = cursor.find_next()
        if not cursor:
            break

        text = cursor.get_text(strip=True) if hasattr(cursor, "get_text") else ""
        if "Afficher plus" in text:
            break

        # Exemple : les titres des événements sont souvent en h4
        if cursor.name == "h4":
            title_tag = cursor
            link_tag = title_tag.find("a")
            title = title_tag.get_text(strip=True)
            url = link_tag["href"] if link_tag and link_tag.has_attr("href") else BASE_URL

            # la date est généralement juste avant le h4
            date_node = title_tag.find_previous(string=True)
            if not date_node:
                continue
            date_text = date_node.strip()
            if not date_text:
                continue

            events.append({"title": title, "url": url, "date_text": date_text})

    return events


def parse_date_range(date_text):
    """
    Transforme '14 Nov 2025' ou '14 - 15 Nov 2025' en (start, end_exclu)
    end_exclu = lendemain pour que ça fasse un événement "journée entière".
    """
    date_text = " ".join(date_text.split())

    if " - " in date_text:
        first, rest = date_text.split(" - ", 1)
        first = first.strip()
        rest = rest.strip()
        end_dt = dateparser.parse(rest, dayfirst=True)
        start_dt = dateparser.parse(f"{first} {end_dt.strftime('%b %Y')}", dayfirst=True)
    else:
        start_dt = dateparser.parse(date_text, dayfirst=True)
        end_dt = start_dt

    return start_dt.date(), (end_dt + timedelta(days=1)).date()


def build_ics(events, calendar_name="Agenda FLSH"):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//Custom//{calendar_name}//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    for ev in events:
        try:
            start_date, end_date = parse_date_range(ev["date_text"])
        except Exception:
            continue

        uid = str(uuid.uuid4()) + "@flsh.uha.fr"
        dtstart = start_date.strftime("%Y%m%d")
        dtend = end_date.strftime("%Y%m%d")
        summary = ev["title"].replace("\n", " ")
        url = ev["url"]

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now}",
            f"DTSTART;VALUE=DATE:{dtstart}",
            f"DTEND;VALUE=DATE:{dtend}",
            f"SUMMARY:{summary}",
            f"URL:{url}",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


if __name__ == "__main__":
    events = fetch_events()
    ics_content = build_ics(events)

    with open("flsh-agenda.ics", "w", encoding="utf-8") as f:
        f.write(ics_content)

    print(f"Généré {len(events)} événements dans flsh-agenda.ics")
