# Bond-OpenAI — actions vocales pour les agents logiciels

Un serveur MCP local donne à Bond, Codex et aux autres clients MCP une action
téléphonique sûre : classifier une tâche, demander les informations manquantes,
faire confirmer l’appel, puis retourner un résultat structuré.

```bash
git clone https://github.com/Caezarr/Bond-OpenAI.git
cd Bond-OpenAI
./scripts/bootstrap.sh
uv run bond-mcp doctor
uv run bond-mcp serve
```

Bond trouve la tâche. Codex comprend l'intention. Fredo passe l'appel.

Pour la démonstration publique, les clés Twilio et Deepgram restent dans le
relay opérateur. Une machine de jury n'a besoin d'aucune clé API si
`demo/profile.json` pointe vers le relay. Voir [docs/DEMO-RELAY.md](docs/DEMO-RELAY.md).

Voir [GOAL-BOND-MCP.md](GOAL-BOND-MCP.md) pour le contrat software et
[GOAL-BOND-DESIGN.md](GOAL-BOND-DESIGN.md) pour le site et la présentation.
