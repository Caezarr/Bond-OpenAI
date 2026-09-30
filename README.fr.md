# Bond-OpenAI — actions vocales pour les agents logiciels

**Un serveur MCP local. N'importe quel agent compatible. Une tâche téléphonique réalisée.**

Bond-OpenAI donne à Bond, Codex et aux autres logiciels compatibles MCP une
action téléphonique sûre. Clonez le dépôt, bootstrappez une fois, connectez le
MCP, et laissez l'agent transformer une tâche telle que « appeler le restaurant
et réserver une table » en une vraie conversation consentie.

## Le produit

```text
Tâche Bond / prompt Codex
        ↓
MCP local Bond-OpenAI
  classifier → clarifier → prévisualiser → appeler
        ↓
Runtime téléphonique Fredo
  Appelant vérifié Twilio + agent vocal Deepgram
        ↓
Résultat structuré retourné à la tâche d'origine
```

Bond trouve le travail. Codex comprend l'intention. Fredo passe l'appel.

## Démarrage rapide

```bash
git clone https://github.com/Caezarr/Bond-OpenAI.git
cd Bond-OpenAI
./scripts/bootstrap.sh
uv run bond-mcp doctor
uv run bond-mcp serve
```

La première exécution installe les dépendances épinglées et les outils locaux.
L'utilisateur ne copie jamais de commandes shell depuis une réponse d'agent et
ne met jamais de secret dans une tâche. Pour la démo publique, les identifiants
fournisseur restent dans le relay opérateur et l'utilisateur n'a besoin que de
la configuration publique `demo/profile.json`. Un fichier `.env` local n'est
requis que lors de l'exécution directe du fournisseur.

## Outils MCP

```text
bond.classify_task(task_text, context)
bond.create_phone_task(task_input, idempotency_key)
bond.get_phone_task_status(call_id)
bond.cancel_phone_task(call_id)
```

Le même contrat fonctionne depuis Bond, Codex, un agent IDE, ou n'importe quel
client MCP. L'adaptateur est local et neutre vis-à-vis du fournisseur ; Fredo
est l'exécuteur téléphonique par défaut.

Voir [docs/MCP.md](docs/MCP.md) pour la configuration client en deux clics.
Voir [docs/DEMO-RELAY.md](docs/DEMO-RELAY.md) pour le flux jury sans identifiants.

## Variables d'environnement

Les variables d'environnement sont documentées dans [.env.example](.env.example) :

- **DEEPGRAM_API_KEY** — clé API Deepgram pour la reconnaissance vocale, le dialogue et la synthèse vocale
- **TWILIO_ACCOUNT_SID**, **TWILIO_AUTH_TOKEN**, **TWILIO_PHONE_NUMBER** — identifiants Twilio pour l'accès PSTN
- **FREDO_ALLOWED_NUMBERS** — destinations consenties exactes, séparées par des virgules, format E.164 canonique
- **FREDO_ENDPOINT_SECRET** — secret de point de terminaison (générer avec `openssl rand -hex 24`)
- **FREDO_PUBLIC_URL** — URL de rappel HTTPS publique pour les tests média Twilio réels
- **FREDO_DEMO_ENDPOINT**, **FREDO_DEMO_ACCESS_TOKEN** — mode jury sans identifiants (valeurs publiées dans `demo/profile.json`)
- **FREDO_HOST**, **FREDO_PORT** — hôte et port du serveur (par défaut 127.0.0.1:8080)
- **FREDO_MAX_DURATION_SECONDS**, **FREDO_MAX_CONCURRENT_CALLS** — limites de sécurité strictes (max 180 secondes, 1 appel concurrent)
- **FREDO_LISTEN_MODEL**, **FREDO_LISTEN_LANGUAGE**, **FREDO_EOT_THRESHOLD**, **FREDO_EOT_TIMEOUT_MS** — configuration de l'agent vocal
- **FREDO_LLM_PROVIDER**, **FREDO_LLM_MODEL** — fournisseur et modèle LLM (par défaut open_ai, gpt-4o-mini)
- **FREDO_VOICE_MODEL** — modèle de synthèse vocale (par défaut aura-2-thalia-en)
- **FREDO_TELEPHONY_PROVIDER** — fournisseur de téléphonie (vide pour auto-sélection du relay démo, `real` pour runtime opérateur local, `mock` pour tests)

## Sécurité par défaut

- un consentement explicite est requis ;
- les destinations E.164 et la liste d'autorisation exacte de Fredo sont appliquées ;
- seule une identité d'appelant vérifiée est utilisée ;
- une confirmation humaine se produit avant la numérotation ;
- un appel actif et un plafond de 180 secondes ;
- l'enregistrement est désactivé ;
- l'agent divulgue sa voix synthétique et l'absence d'enregistrement ;
- les requêtes en double sont idempotentes ;
- l'audio brut, les secrets et les numéros de téléphone complets ne figurent pas dans les journaux.

Rejeter l'aperçu signifie zéro appel opérateur.

## Démo locale

Le répertoire [demo/](demo/) contient les profils de configuration pour les tests locaux :

- **profile.example.json** — modèle de configuration
- **profile.json** — profil actif (pointer vers le relay démo ou configurer un runtime local)

Pour la démonstration publique, les clés Twilio et Deepgram restent dans le
relay opérateur. Une machine de jury n'a besoin d'aucune clé API si
`demo/profile.json` pointe vers le relay. Voir [docs/DEMO-RELAY.md](docs/DEMO-RELAY.md).

## Support

Besoin d'aide pour l'installation, la configuration ou les connexions MCP ? Voir
[SUPPORT.md](SUPPORT.md) pour les liens de documentation et comment poser des
questions en toute sécurité.

Bond-OpenAI est un logiciel libre. Considérez [parrainer le développement sur GitHub](https://github.com/sponsors/Caezarr).

## Objectifs du projet

- [GOAL-BOND-MCP.md](GOAL-BOND-MCP.md) — logiciel et contrat MCP.
- [GOAL-BOND-DESIGN.md](GOAL-BOND-DESIGN.md) — site web, présentation et système visuel.
- [GOAL-BOND-VOICE.md](GOAL-BOND-VOICE.md) — index des objectifs.

## Limite du runtime actuel

Le moteur téléphonique actuel utilise Twilio pour l'accès PSTN et Deepgram pour
la reconnaissance vocale hébergée, le dialogue et la synthèse vocale. Le MCP
lui-même s'exécute localement. Ce dépôt ne revendique pas d'inférence locale,
d'enregistrement, de clonage vocal ou d'appels en masse non surveillés.
