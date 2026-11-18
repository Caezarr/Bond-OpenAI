# Bond-OpenAI : une action téléphonique sûre pour tout agent

[![ci](https://github.com/Caezarr/Bond-OpenAI/actions/workflows/ci.yml/badge.svg)](https://github.com/Caezarr/Bond-OpenAI/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

**Les agents savent lire, écrire et cliquer. Puis le workflow demande un coup de fil, et ils s'arrêtent.**

Un serveur MCP local qui permet à Codex, Bond ou n'importe quel client MCP de passer un appel téléphonique consenti, confirmé par un humain et limité dans le temps, puis de récupérer un résultat structuré dans la tâche. Finaliste du hackathon OpenAI Codex.

*English: [README.md](README.md)*

## Le problème

Réserver un restaurant, relancer une administration, confirmer un rendez-vous, demander un devis à un fournisseur : dans beaucoup de workflows réels, l'étape bloquante n'est pas le raisonnement, c'est d'appeler quelqu'un. L'agent prépare tout jusque-là, puis vous rend la tâche. Lui donner une API de téléphonie brute n'est pas la solution : rien ne l'empêche de composer le mauvais numéro, d'appeler deux fois lors d'un nouvel essai, d'enregistrer sans consentement ou de parler vingt minutes. L'appel doit être une action avec les garanties qu'on attend d'un assistant prudent.

## Comment il le résout

Bond-OpenAI expose le téléphone sous forme de quatre outils MCP avec un flux fixe : **classifier → clarifier → prévisualiser → confirmation explicite → appel vérifié → résultat structuré**.

```text
Tâche d'agent (« appelle le restaurant et réserve une table »)
        ↓  MCP sur stdio
MCP local Bond-OpenAI
  classifier → clarifier → prévisualiser → confirmation explicite → appeler
        ↓
Runtime téléphonique Fredo
  identifiant d'appelant vérifié Twilio + agent vocal Deepgram, plafond 180 s
        ↓
Résultat structuré (statut, issue, résumé) renvoyé à la tâche
```

Décisions de conception clés :

- **Création en deux temps.** `bond.create_phone_task` sans `confirmed: true` renvoie un aperçu et ne stocke rien. Un humain valide, l'agent répète l'appel avec `confirmed: true`. Rejeter l'aperçu signifie zéro appel opérateur.
- **Règles hors du modèle.** Le consentement doit valoir littéralement `true` ; la destination doit être un numéro E.164 canonique présent dans une liste d'autorisation exacte ; l'identifiant d'appelant est toujours le numéro vérifié de l'opérateur. L'entrée de la tâche ne peut changer ni l'appelant, ni l'enregistrement, ni la durée.
- **Idempotent et un seul appel à la fois.** Une clé d'idempotence est obligatoire ; un rejeu renvoie le résultat stocké, une charge modifiée est refusée, une tentative échouée n'est jamais recomposée. Un seul appel actif, garanti dans SQLite entre processus.
- **Cœur neutre vis-à-vis des fournisseurs.** `policy`, `lifecycle` et `store` n'importent ni transport ni SDK fournisseur (verrouillé par un test). Twilio et Deepgram sont derrière l'interface `PhoneProvider`.

## Essayer (2 minutes, sans identifiants)

Prérequis : Python 3.12+ et [uv](https://docs.astral.sh/uv/) (le script de bootstrap installe uv s'il manque, et `cloudflared` via Homebrew si Homebrew est présent).

```bash
git clone https://github.com/Caezarr/Bond-OpenAI.git && cd Bond-OpenAI
./scripts/bootstrap.sh
```

Sans clés fournisseur, le bootstrap se termine par un diagnostic, pas par une erreur à corriger :

```text
  "mcp": "ready",
  "missing": [ "DEEPGRAM_API_KEY", "TWILIO_ACCOUNT_SID", ... ]
No demo relay profile is published. An operator must configure demo/profile.json or local provider variables.
```

Pilotez ensuite le MCP à la main en **mode mock** (opérateur simulé déterministe, aucun réseau). La session classe une tâche, demande un aperçu, le confirme, puis essaie un numéro absent de la liste d'autorisation :

```bash
cat > /tmp/bond-session.jsonl <<'EOF'
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"bond.classify_task","arguments":{"task_text":"Call +15555550100 and reserve a table for two at 8pm"}}}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"bond.create_phone_task","arguments":{"idempotency_key":"demo-1","task_input":{"task_id":"demo-1","caller_identity":"Assistant for Alex","destination_phone":"+15555550100","call_goal":"Reserve a table for two tonight at 8pm","consent_confirmed":true}}}}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"bond.create_phone_task","arguments":{"idempotency_key":"demo-1","task_input":{"task_id":"demo-1","caller_identity":"Assistant for Alex","destination_phone":"+15555550100","call_goal":"Reserve a table for two tonight at 8pm","consent_confirmed":true,"confirmed":true}}}}
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"bond.create_phone_task","arguments":{"idempotency_key":"demo-2","task_input":{"task_id":"demo-2","caller_identity":"x","destination_phone":"+15555550199","call_goal":"x","consent_confirmed":true,"confirmed":true}}}}
EOF
FREDO_TELEPHONY_PROVIDER=mock FREDO_ALLOWED_NUMBERS=+15555550100 FREDO_STATE_DIR="$(mktemp -d)" \
  uv run bond-mcp serve < /tmp/bond-session.jsonl
```

`structuredContent` attendu pour les quatre réponses (le processus garde ensuite son serveur de rappels opérateur ouvert ; arrêtez-le avec Ctrl-C) :

```text
{"classification": "phone_call"}
{"status": "needs_confirmation", "preview": {"destination_phone": "+15555550100", "caller_identity": "Assistant for Alex", "call_goal": "Reserve a table for two tonight at 8pm", "recorded": false, "max_duration_seconds": 180}}
{"task_id": "demo-1", "call_id": "<uuid>", "status": "dialing", "outcome": null, "summary": null, "recorded": false, "error": null, "replayed": false}
{"status": "error", "code": "destination_not_allowed", "message": "Destination is not pre-enrolled"}
```

Lancez la suite de tests hors ligne (opérateur simulé, aucun réseau) :

```bash
uv run pytest      # 90 passed
```

### Appels réels

Un vrai appel PSTN demande un compte Twilio avec un numéro d'appelant vérifié (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`), une clé Deepgram (`DEEPGRAM_API_KEY`), une liste exacte de numéros consentants (`FREDO_ALLOWED_NUMBERS`), un secret de point de terminaison (`FREDO_ENDPOINT_SECRET`) et une URL de rappel HTTPS publique pour Twilio (`FREDO_PUBLIC_URL`). Voir [docs/ENV.md](docs/ENV.md) et [docs/TELEPHONY.md](docs/TELEPHONY.md). `uv run bond-mcp doctor` liste ce qui manque encore.

Autre option : un opérateur héberge le [relay de démo](docs/DEMO-RELAY.md), qui détient les clés fournisseur ; les clients n'ont alors besoin que de l'URL du relay et d'un jeton limité dans `demo/profile.json`. Aucun relay public n'est configuré dans ce dépôt aujourd'hui.

Pour connecter un agent, affichez son entrée MCP avec `uv run bond-mcp install --client codex|bond|generic --print` ([docs/MCP.md](docs/MCP.md)).

## Fonctionnement

| Outil | Rôle |
| --- | --- |
| `bond.classify_task(task_text, context)` | `phone_call`, `needs_input` ou `not_phone_call`. Ne compose jamais. |
| `bond.create_phone_task(task_input, idempotency_key)` | Aperçu sans `confirmed: true` ; avec, exactement un appel par clé d'idempotence. |
| `bond.get_phone_task_status(call_id)` | Résultat structuré : statut, issue, résumé. |
| `bond.cancel_phone_task(call_id)` | Raccroche un appel actif. |

`server.py` est un adaptateur JSON-RPC mince ; `policy.py` valide et classe ; `lifecycle.py` (`PhoneTaskService`) gère aperçu, appel, statut et annulation ; `store.py` conserve les clés d'idempotence et le verrou d'appel unique dans SQLite. `fredo/` est le runtime opérateur : appels REST Twilio, rappel de statut signé et WebSocket média, et un pont vers une session Deepgram Voice Agent qui annonce être une voix synthétique, n'enregistre pas et raccroche en cas de silence. Les états terminaux ne sont jamais écrasés. Les formats d'entrée et de résultat sont dans [schemas/](schemas/).

[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (en anglais) se lit en cinq minutes : composants, machine à états d'un appel, frontières de confiance, et l'endroit où chaque invariant de sécurité est appliqué.

## Preuves dans le dépôt

- **90 tests hors ligne** (`tests/`), sans réseau. Chaque invariant de sécurité de [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#safety-invariants) renvoie au code qui l'applique et est verrouillé par un test : consentement, liste d'autorisation, aperçu avant appel, idempotence et rejeu, pas de recomposition aveugle, un seul appel actif, plafond de 180 s, appelant vérifié, pas d'enregistrement, rappels signés, aucun secret dans les résultats.
- **Contrôles statiques :** `ruff` (lint et format), `mypy`.
- **CI** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) lance lint, format, mypy, pytest et `uv build` à chaque push et pull request.
- Décision de conception : [docs/decisions/0001-verified-caller-identity.md](docs/decisions/0001-verified-caller-identity.md).

## Limites et état

- Un appel à la fois, 180 secondes au maximum. C'est une action encadrée, pas un composeur automatique, et il n'y a pas d'appels en masse non surveillés.
- La reconnaissance vocale, le dialogue et la synthèse sont hébergés par Deepgram ; le PSTN passe par Twilio. Aucune inférence locale, pas d'enregistrement ni de clonage vocal.
- Le statut est cohérent à terme entre rappels et interrogations ; la première valeur terminale l'emporte.
- Le stockage SQLite est local à une machine ; le relay de démo a son propre stockage.
- Version 0.1.0. Versions et alternatives des fournisseurs : [docs/PROVIDER-MATRIX.md](docs/PROVIDER-MATRIX.md).

## Développement

```bash
uv sync --frozen --extra dev
uv run ruff check src tests && uv run ruff format --check src tests
uv run mypy
uv run pytest        # hors ligne : opérateur simulé, aucun réseau
uv build
```

Aide et signalement sûr des problèmes : [SUPPORT.md](SUPPORT.md), [SECURITY.md](SECURITY.md). Contributions : [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

[Apache License 2.0](LICENSE). Mentions tierces : [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
