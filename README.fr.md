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

Pour la démonstration publique, les clés Twilio et Deepgram restent dans le
relay opérateur. Une machine de jury n'a besoin d'aucune clé API si
`demo/profile.json` pointe vers le relay. Voir [docs/DEMO-RELAY.md](docs/DEMO-RELAY.md).

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

Voir [GOAL-BOND-MCP.md](GOAL-BOND-MCP.md) pour le contrat software et
[GOAL-BOND-DESIGN.md](GOAL-BOND-DESIGN.md) pour le site et la présentation.
