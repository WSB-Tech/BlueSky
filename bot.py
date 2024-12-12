import os
import json
from datetime import datetime
from atproto import Client
from dotenv import load_dotenv
import time
from pytz import timezone
import requests
from atproto_client.models.app.bsky.graph.get_list import Params

# Debugging-Modus basierend auf Umgebungsvariable
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() in ("true", "1", "yes")
LOCAL_TIMEZONE = timezone("Europe/Berlin")  # Lokale Zeitzone, anpassbar

def debug_print(message):
    if DEBUG_MODE:
        print(f"DEBUG: {message}")

# .env-Datei laden
load_dotenv()

USERNAME = os.getenv("BLUESKY_USERNAME")
PASSWORD = os.getenv("BLUESKY_PASSWORD")

def test_api_connection():
    try:
        response = requests.get("https://bsky.social", timeout=10)
        if response.status_code == 200:
            print("BlueSky API ist erreichbar.")
        else:
            print(f"BlueSky API gibt Status-Code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Netzwerkproblem: {e}")

# Test der API-Verbindung vor Start
print("Prüfe API-Verbindung...")
test_api_connection()

# BlueSky-Client initialisieren und einloggen
try:
    if not USERNAME or not PASSWORD:
        raise ValueError("Benutzername oder Passwort nicht in der .env-Datei definiert.")

    debug_print(f"Benutzername geladen: {USERNAME}")  # Passwort nicht aus Sicherheitsgründen

    client = Client()
    client.login(USERNAME, PASSWORD)
    print("Authentifizierung erfolgreich!")
except Exception as e:
    print(f"Fehler bei der Authentifizierung: {str(e)}")
    exit(1)

# Keywords laden
def load_keywords(filename="keywords.json"):
    try:
        with open(filename, "r") as file:
            keywords = json.load(file)
        print("Keywords erfolgreich geladen.")
        return keywords
    except FileNotFoundError:
        print(f"Keywords-Datei {filename} nicht gefunden. Standardwerte werden verwendet.")
        return {
            "critical_keywords": {},
            "contextual_keywords": {},
            "positive_keywords": []
        }
    except Exception as e:
        print(f"Fehler beim Laden der Keywords: {e}")
        return {
            "critical_keywords": {},
            "contextual_keywords": {},
            "positive_keywords": []
        }

keywords = load_keywords()
CRITICAL_KEYWORDS = keywords.get("critical_keywords", {})
CONTEXTUAL_KEYWORDS = keywords.get("contextual_keywords", {})
POSITIVE_KEYWORDS = keywords.get("positive_keywords", [])

def load_local_list(filename):
    try:
        if not os.path.exists(filename):
            debug_print(f"Datei {filename} existiert nicht. Eine neue Datei wird erstellt.")
            with open(filename, "w") as file:
                json.dump([], file, indent=4)
            return []
        with open(filename, "r") as file:
            return json.load(file)
    except Exception as e:
        print(f"Fehler beim Laden der Liste {filename}: {e}")
        return []


def save_local_list(data, filename):
    try:
        with open(filename, "w") as file:
            json.dump(data, file, indent=4)
        debug_print(f"Liste in {filename} erfolgreich gespeichert.")
    except Exception as e:
        print(f"Fehler beim Speichern in die Datei {filename}: {e}")

def get_local_timestamp():
    return datetime.now(LOCAL_TIMEZONE).isoformat()

def log_action(action, user, handle, details):
    # Kompakte Darstellung von bio_hits und post_hits, wenn keine Treffer vorliegen
    def simplify_hits(hits):
        if isinstance(hits, dict) and not any(hits.values()):  # Keine Treffer in der Struktur
            return "no hits"
        return hits

    details["bio_hits"] = simplify_hits(details.get("bio_hits", {}))
    details["post_hits"] = simplify_hits(details.get("post_hits", {}))

    log_entry = {
        "timestamp": get_local_timestamp(),
        "action": action,
        "user": user,
        "handle": handle,
        "details": details
    }

    try:
        logs = load_local_list("log.json")
        logs.append(log_entry)
        save_local_list(logs, "log.json")
        debug_print(f"Aktion geloggt: {log_entry}")
    except Exception as e:
        print(f"Fehler beim Schreiben in die Log-Datei: {e}")


def save_to_list(filename, did, action, handle, details):
    try:
        data = load_local_list(filename)
        if did not in data:
            data.append(did)
            save_local_list(data, filename)
            log_action(action, did, handle, details)
            print(f"Benutzer {did} zur Liste {filename} hinzugefügt.")
        else:
            debug_print(f"Benutzer {did} ist bereits in der Liste {filename}.")
    except Exception as e:
        print(f"Fehler beim Hinzufügen von {did} zur Liste {filename}: {e}")

def retry_request(func, *args, retries=2, delay=2, **kwargs):
    for attempt in range(retries):
        try:
            result = func(*args, **kwargs)
            debug_print(f"API-Aufruf erfolgreich: {result}")
            return result
        except TypeError as te:
            debug_print(f"Fehler: Möglicherweise fehlen Parameter. {te}")
            break
        except Exception as e:
            debug_print(f"Fehler bei API-Aufruf (Versuch {attempt + 1}): {e}")
            if "429" in str(e):
                print(f"Rate-Limiting erkannt. Warte {delay} Sekunden...")
            time.sleep(delay)
    print(f"Alle {retries} Versuche fehlgeschlagen.")
    return None

def resolve_handle_to_did(identifier):
    if identifier.startswith("did:"):
        debug_print(f"Versuche DID direkt zu verwenden: {identifier}")
        # Übergabe der Parameter als Dictionary
        response = retry_request(client.app.bsky.actor.get_profile, params={"actor": identifier})
        if response:
            handle = getattr(response, "handle", None)
            debug_print(f"DID '{identifier}' aufgelöst zu Handle: {handle}")
            return identifier, handle
    else:
        debug_print(f"Versuche Handle '{identifier}' aufzulösen.")
        response = retry_request(client.com.atproto.identity.resolve_handle, params={"handle": identifier})
        debug_print(f"API-Response für Handle-Resolution: {response}")
        if response and hasattr(response, "did"):
            did = response.did
            debug_print(f"Handle '{identifier}' aufgelöst zu DID: {did}")
            return did, identifier
    debug_print(f"Fehler: Handle/DID '{identifier}' konnte nicht aufgelöst werden.")
    return None, None


def get_profile(did):
    try:
        debug_print(f"Rufe Profil für DID {did} ab.")
        response = retry_request(client.app.bsky.actor.get_profile, params={"actor": did})
        if response:
            debug_print(f"Profil abgerufen für DID {did}: {response}")
            return response
        else:
            debug_print(f"Profil für DID {did} nicht gefunden.")
    except Exception as e:
        debug_print(f"Fehler beim Abrufen des Profils für DID {did}: {e}")
    log_action("profile_fetch_error", did, None, {"error": "Profil konnte nicht abgerufen werden"})
    return None


def fetch_user_posts(did):
    response = retry_request(client.app.bsky.feed.get_author_feed, actor=did)
    if response and hasattr(response, "feed"):
        debug_print(f"Beiträge abgerufen für DID {did}: {response}")
        return response.feed
    debug_print(f"Keine Beiträge für DID {did} gefunden.")
    return []

def fetch_followers(did):
    try:
        # Erstelle das Parameter-Objekt
        params = {"actor": did}
        debug_print(f"Rufe Follower ab für DID: {did} mit Parametern: {params}")
        
        # API-Aufruf mit Parameter als Ganzes übergeben
        response = retry_request(client.app.bsky.graph.get_follows, params=params)
        debug_print(f"API-Response für Follower: {response}")

        # Verarbeite die Response
        if response and hasattr(response, "follows"):
            return [follower.did for follower in response.follows]
        else:
            debug_print(f"Keine Follower für DID {did} gefunden.")
            return []
    except Exception as e:
        print(f"Fehler beim Abrufen der Follower für DID {did}: {e}")
        return []


def fetch_bsky_moderation_list():
    try:
        at_uri = "did:plc:5e7wgl45gdnxtfw2h36iemzz/app.bsky.graph.list/3lcy2vfsbpq2u"
        debug_print(f"Rufe Moderationsliste ab mit AT-URI: {at_uri}")

        params = Params(list=at_uri)
        response = retry_request(client.app.bsky.graph.get_list, params=params)

        if response and hasattr(response, "items"):
            return [item.subject.did for item in response.items]
        else:
            debug_print("Keine Einträge in der BlueSky-Moderationsliste gefunden.")
            return []
    except Exception as e:
        print(f"Fehler beim Abrufen der BlueSky-Moderationsliste: {e}")
        return []
    
def calculate_profile_score(profile, posts):
    if not profile:
        debug_print("Profil ist None. Keine Berechnung möglich.")
        return {"score": 0, "critical_hits": 0, "contextual_hits": 0, "details": {"bio_hits": "no hits", "post_hits": "no hits"}}

    score = 0
    critical_hits = 0
    contextual_hits = 0
    details = {"bio_hits": {"critical": [], "contextual": [], "positive": []}, "post_hits": {"critical": [], "contextual": [], "positive": []}}

    bio = ""
    if hasattr(profile, "description") and profile.description:
        bio = profile.description.lower()
    else:
        debug_print("Profil hat keine Beschreibung.")

    for keyword, weight in CRITICAL_KEYWORDS.items():
        if keyword in bio:
            score += weight
            critical_hits += 1
            details["bio_hits"]["critical"].append({"keyword": keyword, "weight": weight})
    for keyword, weight in CONTEXTUAL_KEYWORDS.items():
        if keyword in bio:
            score += weight
            contextual_hits += 1
            details["bio_hits"]["contextual"].append({"keyword": keyword, "weight": weight})
    for keyword in POSITIVE_KEYWORDS:
        if keyword in bio:
            score -= 2
            details["bio_hits"]["positive"].append({"keyword": keyword, "weight": -2})

    for post in posts:
        content = getattr(post.record, "text", "").lower() if hasattr(post, "record") else ""
        for keyword, weight in CRITICAL_KEYWORDS.items():
            if keyword in content:
                score += weight
                critical_hits += 1
                details["post_hits"]["critical"].append({"keyword": keyword, "weight": weight})
        for keyword, weight in CONTEXTUAL_KEYWORDS.items():
            if keyword in content:
                score += weight
                contextual_hits += 1
                details["post_hits"]["contextual"].append({"keyword": keyword, "weight": weight})
        for keyword in POSITIVE_KEYWORDS:
            if keyword in content:
                score -= 2
                details["post_hits"]["positive"].append({"keyword": keyword, "weight": -2})

    debug_print(f"Score berechnet: {score} (Critical: {critical_hits}, Contextual: {contextual_hits})")
    return {"score": score, "critical_hits": critical_hits, "contextual_hits": contextual_hits, "details": details}

def analyze_user(identifier, analyzed_users, moderation_list_file, suspect_list_file, whitelist_file="whitelist.json"):
    # Lade die Whitelist
    whitelist = load_local_list(whitelist_file)

    # Versuche, DID und Handle aufzulösen
    did, handle = resolve_handle_to_did(identifier)
    if not did:
        print(f"Fehler: Konnte DID für '{identifier}' nicht auflösen.")
        log_action("resolve_handle_failed", identifier, None, {"error": "DID konnte nicht aufgelöst werden"})
        return

    # Überspringe Benutzer, die bereits in der Whitelist sind
    if did in whitelist:
        debug_print(f"Benutzer {did} ist auf der Whitelist. Überspringe Analyse.")
        return

    # Überspringe Benutzer, die bereits analysiert wurden
    if did in analyzed_users:
        debug_print(f"Benutzer {did} wurde bereits analysiert. Überspringe.")
        return

    # Hole das Profil
    profile = get_profile(did)
    if not profile:
        print(f"Profil konnte für Benutzer ({did}, {handle}) nicht geladen werden. Überspringe.")
        log_action("profile_not_found", did, handle, {"error": "Profil konnte nicht abgerufen werden"})
        return

    # Hole die Posts und berechne den Score
    posts = fetch_user_posts(did)
    analysis = calculate_profile_score(profile, posts)

    # Benutzer mit Score von -4 oder weniger zur Whitelist hinzufügen
    if analysis["score"] <= -4:
        debug_print(f"Benutzer {did} hat einen Score von {analysis['score']}. Zur Whitelist hinzufügen.")
        save_to_list(whitelist_file, did, "add_to_whitelist", handle, analysis["details"])
        return

    # Benutzer je nach Score zu Moderations- oder Verdachtsliste hinzufügen
    if analysis["score"] >= 10:
        save_to_list(moderation_list_file, did, "add_to_moderation_list", handle, analysis["details"])
    elif analysis["score"] >= 5:
        save_to_list(suspect_list_file, did, "add_to_suspect_list", handle, analysis["details"])
    else:
        log_action("no_action", did, handle, analysis["details"])

    # Benutzer als analysiert markieren
    analyzed_users.add(did)
    save_local_list(list(analyzed_users), "analyzed_users.json")


def main():
    moderation_list_file = "moderation_list.json"
    suspect_list_file = "suspect_list.json"
    start_users = load_local_list("start_users.json")
    analyzed_users = set(load_local_list("analyzed_users.json"))

    # Startbenutzer und deren Follower analysieren
    for user in start_users:
        analyze_user(user, analyzed_users, moderation_list_file, suspect_list_file)
        followers = fetch_followers(user)
        for follower in followers:
            analyze_user(follower, analyzed_users, moderation_list_file, suspect_list_file)

    # Follower von Benutzern auf der Moderationsliste analysieren
    moderation_list = fetch_bsky_moderation_list()
    for user in moderation_list:
        followers = fetch_followers(user)
        for follower in followers:
            analyze_user(follower, analyzed_users, moderation_list_file, suspect_list_file)

    print("Analyse abgeschlossen.")

if __name__ == "__main__":
    main()
