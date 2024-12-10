---

## **BlueSky Moderation Bot**

### **Überblick**
Ein Python-basierter Moderationsbot für die BlueSky-Plattform. Der Bot verwendet die BlueSky-API, um problematische Accounts zu analysieren und in passende Listen einzutragen:
- **Hate accs and mutuals**: Accounts, die gemeldet oder geblockt werden sollen.
- **Verdachtsliste**: Accounts zur Überprüfung.
- **Whitelist**: Vertrauenswürdige Accounts, die ignoriert werden.

Der Bot basiert auf einer Schlüsselwortanalyse (Keywords) und verwendet Scoring, um problematische Inhalte zu identifizieren.

---

### **Funktionen**
- **Automatisches Erstellen und Verwalten von Listen:**
  - **Hate accs and mutuals**: Für problematische Accounts und Netzwerke.
  - **Verdachtsliste**: Für Accounts, die manuell überprüft werden sollen.
  - **Whitelist**: Accounts, die der Bot nicht analysieren soll.
- **Schlüsselwortanalyse:**
  - Bewertet Bio und Beiträge von Nutzern basierend auf definierten Keywords.
- **Score-basierte Entscheidungen:**
  - Accounts mit einem hohen Score landen in der Moderationsliste.
  - Accounts mit mittlerem Score landen in der Verdachtsliste.
- **Manuelle Pflege der Whitelist:**
  - Die Whitelist wird ausschließlich manuell gepflegt.
- **Protokollierung:** 
  - Alle Aktionen (Hinzufügen zu Listen, Überspringen von Accounts) werden in einer JSON-Log-Datei gespeichert.

---

### **Anforderungen**

1. **Python-Version:**  
   - Python 3.10 oder höher

2. **Abhängigkeiten:**  
   Installiere die benötigten Pakete mit:
   ```bash
   pip install -r requirements.txt
   ```
   **Erforderliche Pakete:**
   - `atproto`
   - `python-dotenv`

3. **BlueSky-API-Zugang:**  
   - Ein gültiger Benutzername und ein Passwort für die BlueSky-API.

4. **Dateien:**  
   - **`.env`**: Für API-Zugangsdaten.
   - **`keywords.json`**: Für Keywords und Gewichtungen.

---

### **Setup**

1. **Umgebungsvariablen einrichten**
   Erstelle eine Datei namens `.env` im Projektverzeichnis mit folgendem Inhalt:
   ```env
   BLUESKY_USERNAME=dein_benutzername
   BLUESKY_PASSWORD=dein_passwort
   ```

2. **Keywords definieren**
   Erstelle eine Datei `keywords.json` im selben Verzeichnis:
   ```json
   {
     "critical_keywords": {
       "hass": 3,
       "gewalt": 3
     },
     "contextual_keywords": {
       "nazi": 1,
       "rechte": 1
     },
     "positive_keywords": [
       "journalist",
       "recherche"
     ]
   }
   ```

3. **Bot starten**
   Starte den Bot mit:
   ```bash
   python bot.py
   ```

---

### **Funktionsweise**

1. **Login in BlueSky:**  
   Der Bot authentifiziert sich mit den in der `.env`-Datei hinterlegten Zugangsdaten.

2. **Automatische Listenverwaltung:**  
   - Der Bot erstellt die Listen `Hate accs and mutuals`, `Verdachtsliste` und `Whitelist`, falls sie nicht existieren.

3. **Analyse von Nutzern:**  
   - Überprüft die Bio und Beiträge eines Nutzers basierend auf den definierten Keywords.
   - Berechnet einen Score, um den Nutzer in die passende Liste einzutragen.

4. **Score-basierte Logik:**  
   - **Score ≥ 5**: Account wird der Moderationsliste (`Hate accs and mutuals`) hinzugefügt.  
   - **Score ≥ 3, aber < 5**: Account wird der Verdachtsliste hinzugefügt.  
   - **Auf der Whitelist**: Account wird ignoriert.

5. **Protokollierung:**  
   - Aktionen werden in `log.json` dokumentiert.

---

### **Beispielablauf**

1. **Beispiel-Keywords:**  
   - Bio enthält: `"Nazi-Strukturen analysieren"`  
   - Beiträge enthalten: `"Gewalt wird verherrlicht"`

2. **Analyse:**  
   - Score aus der Bio: 1 (für "rechte").  
   - Score aus den Beiträgen: 3 (für "Gewalt").  
   - Gesamtscore: 4.  

3. **Entscheidung:**  
   - Nutzer wird der **Verdachtsliste** hinzugefügt.

---

### **Log-Datei**
Alle Aktionen werden in einer JSON-Datei `log.json` gespeichert. Beispiel:
```json
{
  "action": "add_to_moderation_list",
  "did": "did:plc:exampleuser",
  "reason": "Erfüllt Schwellenwert",
  "timestamp": "2024-12-10 14:30:00"
}
```

---

### **Geplante Erweiterungen**
- Implementierung einer Follower-Analyse für Mutuals.
- Erweiterte Unterstützung für dynamische Keyword-Anpassung während der Laufzeit.
- Benachrichtigungen bei neuen Verdachtsfällen.

---

**Autor:**  
Ein enthusiastischer BlueSky-Entwickler 😊  
**Lizenz:**  
MIT

---
