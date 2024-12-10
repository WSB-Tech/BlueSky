import os
import json
from datetime import datetime
from atproto import Client
from dotenv import load_dotenv

# Debugging-Modus basierend auf Umgebungsvariable
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() in ("true", "1", "yes")

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
CRITICAL_KEYWORDS = keywords["critical_keywords"]
CONTEXTUAL_KEYWORDS = keywords["contextual_keywords"]
POSITIVE_KEYWORDS = keywords["positive_keywords"]

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

def log_action(action, user, handle, details=""):
    log_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
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

def resolve_handle_to_did(identifier):
    if identifier.startswith("did:"):
        try:
            response = client.app.bsky.actor.get_profile({"actor": identifier})
            handle = getattr(response, "handle", None)
            debug_print(f"DID '{identifier}' aufgelöst zu Handle: {handle}")
            return identifier, handle
        except Exception as e:
            print(f"Fehler beim Auflösen des Handles für DID '{identifier}': {e}")
            return identifier, None
    else:
        try:
            response = client.com.atproto.identity.resolve_handle({"handle": identifier})
            if hasattr(response, "did"):
                did = response.did
                debug_print(f"Handle '{identifier}' aufgelöst zu DID: {did}")
                return did, identifier
            else:
                debug_print(f"Fehler: Kein DID in der Antwort für Handle '{identifier}'")
                return None, identifier
        except Exception as e:
            print(f"Fehler beim Auflösen des Handles '{identifier}': {e}")
            return None, identifier

def get_profile(did):
    try:
        response = client.app.bsky.actor.get_profile({"actor": did})
        debug_print(f"Profil abgerufen für DID {did}: {response}")
        return response
    except Exception as e:
        print(f"Fehler beim Abrufen des Profils für {did}: {e}")
        return None

def fetch_user_posts_and_replies(did):
    try:
        response = client.app.bsky.feed.get_author_feed({"actor": did})
        debug_print(f"Beiträge abgerufen für DID {did}: {response}")
        return response.feed if hasattr(response, "feed") else []
    except Exception as e:
        print(f"Fehler beim Abrufen der Beiträge für {did}: {e}")
        return []

def fetch_followers(did):
    try:
        response = client.app.bsky.graph.get_follows({"actor": did})
        debug_print(f"Follower abgerufen für DID {did}: {response}")
        return [follower.did for follower in response.follows]
    except Exception as e:
        print(f"Fehler beim Abrufen der Follower für {did}: {e}")
        return []

def calculate_profile_score(profile, posts):
    score = 0
    critical_hits = 0
    contextual_hits = 0

    bio = getattr(profile, "description", "").lower() if profile else ""
    for keyword, weight in CRITICAL_KEYWORDS.items():
        if keyword in bio:
            score += weight
            critical_hits += 1
    for keyword, weight in CONTEXTUAL_KEYWORDS.items():
        if keyword in bio:
            score += weight
            contextual_hits += 1

    for post in posts:
        content = getattr(post.record, "text", "").lower() if hasattr(post, "record") else ""
        for keyword, weight in CRITICAL_KEYWORDS.items():
            if keyword in content:
                score += weight
                critical_hits += 1
        for keyword, weight in CONTEXTUAL_KEYWORDS.items():
            if keyword in content:
                score += weight
                contextual_hits += 1

    for keyword in POSITIVE_KEYWORDS:
        if keyword in bio:
            score -= 2

    debug_print(f"Score berechnet: {score} (Critical: {critical_hits}, Contextual: {contextual_hits})")
    return {"score": score, "critical_hits": critical_hits, "contextual_hits": contextual_hits}

def analyze_user(identifier, analyzed_users, moderation_list_file, suspect_list_file, whitelist_file):
    did, handle = resolve_handle_to_did(identifier)
    if not did:
        print(f"Fehler: Konnte DID für '{identifier}' nicht auflösen.")
        return

    debug_print(f"Analysiere Benutzer: {did} ({handle})")

    if did in analyzed_users:
        debug_print(f"Benutzer {did} wurde bereits analysiert. Überspringe.")
        return

    profile = get_profile(did)
    posts = fetch_user_posts_and_replies(did)

    analysis = calculate_profile_score(profile, posts)
    if analysis["score"] >= 10 and analysis["critical_hits"] >= 3:
        print(f"Benutzer {did} erfüllt Kriterien für die Moderationsliste.")
        moderation_list = load_local_list(moderation_list_file)
        if did not in moderation_list:
            moderation_list.append(did)
            save_local_list(moderation_list, moderation_list_file)
        log_action("add_to_moderation_list", did, handle, f"Score: {analysis['score']}")
    elif analysis["score"] >= 5:
        print(f"Benutzer {did} wird zur Verdachtsliste hinzugefügt.")
        suspect_list = load_local_list(suspect_list_file)
        if did not in suspect_list:
            suspect_list.append(did)
            save_local_list(suspect_list, suspect_list_file)
        log_action("add_to_suspect_list", did, handle, f"Score: {analysis['score']}")
    elif analysis["score"] <= -4:
        print(f"Benutzer {did} wird zur Whitelist hinzugefügt.")
        whitelist = load_local_list(whitelist_file)
        if did not in whitelist:
            whitelist.append(did)
            save_local_list(whitelist, whitelist_file)
        log_action("add_to_whitelist", did, handle, f"Score: {analysis['score']}")
    else:
        log_action("no_action", did, handle, f"Score: {analysis['score']}")

    analyzed_users.append(did)
    save_local_list(analyzed_users, "analyzed_users.json")

def main():
    moderation_list_file = "moderation_list.json"
    suspect_list_file = "suspect_list.json"
    whitelist_file = "whitelist.json"
    start_users = load_local_list("start_users.json")
    analyzed_users = load_local_list("analyzed_users.json")

    for user in start_users:
        analyze_user(user, analyzed_users, moderation_list_file, suspect_list_file, whitelist_file)
        followers = fetch_followers(user)
        for follower in followers:
            analyze_user(follower, analyzed_users, moderation_list_file, suspect_list_file, whitelist_file)

if __name__ == "__main__":
    main()
