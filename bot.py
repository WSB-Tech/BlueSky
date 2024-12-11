import os
import json
from datetime import datetime
from atproto import Client
from dotenv import load_dotenv
import time
from pytz import timezone

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

# BlueSky-Client initialisieren und einloggen
try:
    client = Client()
    client.login(USERNAME, PASSWORD)
    print("Authentifizierung erfolgreich!")
except Exception as e:
    print(f"Fehler bei der Authentifizierung: {e}")
    exit(1)

# Keywords laden
def load_keywords(filename="keywords.json"):
    try:
        with open(filename, "r") as file:
            keywords = json.load(file)
        print("Keywords erfolgreich geladen.")
        return keywords
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
        with open(filename, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        debug_print(f"Datei {filename} nicht gefunden. Eine neue wird erstellt.")
        with open(filename, "w") as file:
            json.dump([], file, indent=4)
        return []
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

def log_action(action, user, handle, details=""):
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

def retry_request(func, *args, retries=3, delay=5, **kwargs):
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if "429" in str(e):
                print(f"Rate-Limiting erkannt. Warte {delay} Sekunden...")
            else:
                print(f"Fehler bei Versuch {attempt + 1}: {e}")
            time.sleep(delay)
    print(f"Alle {retries} Versuche fehlgeschlagen.")
    return None

def resolve_handle_to_did(identifier):
    if identifier.startswith("did:"):
        response = retry_request(client.app.bsky.actor.get_profile, {"actor": identifier})
        if response:
            handle = getattr(response, "handle", None)
            debug_print(f"DID '{identifier}' aufgelöst zu Handle: {handle}")
            return identifier, handle
    else:
        response = retry_request(client.com.atproto.identity.resolve_handle, {"handle": identifier})
        if response and hasattr(response, "did"):
            did = response.did
            debug_print(f"Handle '{identifier}' aufgelöst zu DID: {did}")
            return did, identifier
    debug_print(f"Fehler: Handle/DID '{identifier}' konnte nicht aufgelöst werden.")
    return None, None

def get_profile(did):
    response = retry_request(client.app.bsky.actor.get_profile, {"actor": did})
    if response:
        debug_print(f"Profil abgerufen für DID {did}: {response}")
        return response
    log_action("profile_fetch_error", did, None, "Profil konnte nicht abgerufen werden")
    return None

def fetch_user_posts(did):
    response = retry_request(client.app.bsky.feed.get_author_feed, {"actor": did})
    if response and hasattr(response, "feed"):
        debug_print(f"Beiträge abgerufen für DID {did}: {response}")
        return response.feed
    debug_print(f"Keine Beiträge für DID {did} gefunden.")
    return []

def fetch_followers(did):
    response = retry_request(client.app.bsky.graph.get_follows, {"actor": did})
    if response and hasattr(response, "follows"):
        debug_print(f"Follower abgerufen für DID {did}: {response}")
        return [follower.did for follower in response.follows]
    debug_print(f"Keine Follower für DID {did} gefunden.")
    return []

def calculate_profile_score(profile, posts):
    score = 0
    critical_hits = 0
    contextual_hits = 0
    details = {"bio_hits": {"critical": [], "contextual": [], "positive": []}, "post_hits": {"critical": [], "contextual": [], "positive": []}}

    bio = getattr(profile, "description", "").lower() if profile and hasattr(profile, "description") else ""
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

def analyze_user(identifier, analyzed_users, moderation_list_file, suspect_list_file):
    did, handle = resolve_handle_to_did(identifier)
    if not did:
        print(f"Fehler: Konnte DID für '{identifier}' nicht auflösen.")
        return

    if did in analyzed_users:
        debug_print(f"Benutzer {did} wurde bereits analysiert. Überspringe.")
        return

    profile = get_profile(did)
    if not profile:
        print(f"Profil konnte für Benutzer {did} nicht geladen werden. Überspringe.")
        log_action("profile_not_found", did, handle, "Profil konnte nicht abgerufen werden")
        return

    posts = fetch_user_posts(did)
    analysis = calculate_profile_score(profile, posts)

    if analysis["score"] >= 10:
        save_to_list(moderation_list_file, did, "add_to_moderation_list", handle, analysis["details"])
    elif analysis["score"] >= 5:
        save_to_list(suspect_list_file, did, "add_to_suspect_list", handle, analysis["details"])
    else:
        log_action("no_action", did, handle, analysis["details"])

    analyzed_users.add(did)
    save_local_list(list(analyzed_users), "analyzed_users.json")

def main():
    moderation_list_file = "moderation_list.json"
    suspect_list_file = "suspect_list.json"
    start_users = load_local_list("start_users.json")
    analyzed_users = set(load_local_list("analyzed_users.json"))

    for user in start_users:
        analyze_user(user, analyzed_users, moderation_list_file, suspect_list_file)
        followers = fetch_followers(user)
        for follower in followers:
            analyze_user(follower, analyzed_users, moderation_list_file, suspect_list_file)

if __name__ == "__main__":
    main()
