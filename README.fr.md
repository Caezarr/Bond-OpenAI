# Bond-OpenAI — actions vocales pour les agents logiciels

**Les agents savent lire, écrire et cliquer. Puis le workflow demande un coup de fil, et ils s'arrêtent.**

Réserver un restaurant, relancer une administration, confirmer un rendez-vous,
demander un devis à un fournisseur : dans énormément de workflows réels,
l'étape bloquante n'est pas le raisonnement, c'est d'appeler quelqu'un.
Bond-OpenAI lève ce blocage. Il donne à Bond, Codex et à tout agent compatible
MCP une action téléphonique sûre, pour que l'agent termine la tâche au lieu de
vous la rendre.

**Un serveur MCP local. N'importe quel agent compatible. Une tâche téléphonique réalisée.**

Clonez le dépôt, bootstrappez une fois, connectez le
MCP, et laissez l'agent transformer une tâche telle que « appeler le restaurant
et réserver une table » en une vraie conversation consentie.

## Le produit

```text
Tâche Bond / prompt Codex
        ↓
MCP local Bond-OpenAI
  classifier → clarifier → prévisualiser → confirmation explicite → appeler
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

| Outil | Rôle |
| --- | --- |
| `bond.classify_task(task_text, context)` | Indique si une tâche nécessite un appel (`phone_call`, `needs_input`, `not_phone_call`). Ne compose jamais. |
| `bond.create_phone_task(task_input, idempotency_key)` | Sans `confirmed: true`, renvoie un aperçu et ne compose rien. Avec, passe exactement un appel par clé d'idempotence. |
| `bond.get_phone_task_status(call_id)` | Renvoie le résultat structuré : statut, issue, résumé. |
| `bond.cancel_phone_task(call_id)` | Raccroche un appel actif. |

Le même contrat fonctionne depuis Bond, Codex, un agent IDE ou n'importe quel
client MCP. Les formats d'entrée et de résultat sont dans [schemas/](schemas/) ;
la configuration client est dans [docs/MCP.md](docs/MCP.md), le flux jury sans
identifiants dans [docs/DEMO-RELAY.md](docs/DEMO-RELAY.md), et toutes les
variables d'environnement dans [docs/ENV.md](docs/ENV.md).

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

- un consentement explicite du destinataire est requis ;
- les destinations doivent être des numéros E.164 canoniques présents dans une liste d'autorisation exacte ;
- seul l'identifiant d'appelant vérifié de l'opérateur est utilisé ;
- un humain confirme l'aperçu avant la numérotation ; le rejeter signifie zéro appel opérateur ;
- un seul appel actif, plafonné à 180 secondes à la fois par Twilio et par le runtime ;
- l'enregistrement est désactivé, et l'agent annonce qu'il est une voix synthétique et n'enregistre pas ;
- la création exige une clé d'idempotence ; une tentative échouée n'est jamais recomposée automatiquement ;
- les rappels Twilio sont vérifiés par signature ;
- l'audio brut, les secrets et les numéros complets ne figurent ni dans les journaux ni dans les résultats.

L'endroit du code où chaque règle est appliquée, et les tests hors ligne qui les verrouillent,
sont listés dans [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#safety-invariants) (en anglais).

## Architecture

```text
src/bond_mcp/server.py      adaptateur MCP (JSON-RPC sur stdio)
src/bond_mcp/lifecycle.py   cœur neutre : aperçu, appel, statut, annulation
src/bond_mcp/policy.py      consentement, E.164, liste d'autorisation, classification
src/bond_mcp/store.py       SQLite : idempotence + un seul appel actif
src/bond_mcp/providers.py   Fredo (Twilio + Deepgram en local) ou relay démo
src/fredo/                  runtime opérateur : téléphonie, agent vocal, gestion des silences
```

[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) se lit en cinq minutes :
composants, machine à états d'un appel, frontières de confiance et invariants
de sécurité.

## Développement

```bash
uv sync --frozen --extra dev
uv run ruff check src tests && uv run ruff format --check src tests
uv run mypy
uv run pytest        # hors ligne : opérateur simulé, aucun réseau
uv build
```

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

- [GOAL-BOND-MCP.md](docs/goals/GOAL-BOND-MCP.md) — logiciel et contrat MCP.
- [GOAL-BOND-DESIGN.md](docs/goals/GOAL-BOND-DESIGN.md) — site web, présentation et système visuel.
- [GOAL-BOND-VOICE.md](docs/goals/GOAL-BOND-VOICE.md) — index des objectifs.

## Limite du runtime actuel

Le moteur téléphonique actuel utilise Twilio pour l'accès PSTN et Deepgram pour
la reconnaissance vocale hébergée, le dialogue et la synthèse vocale. Le MCP
lui-même s'exécute localement. Ce dépôt ne revendique pas d'inférence locale,
d'enregistrement, de clonage vocal ou d'appels en masse non surveillés.
