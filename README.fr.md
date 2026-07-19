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

Bond trouve la tâche. Codex comprend l’intention. Fredo passe l’appel.

Voir [GOAL-BOND-MCP.md](GOAL-BOND-MCP.md) pour le contrat software et
[GOAL-BOND-DESIGN.md](GOAL-BOND-DESIGN.md) pour le site et la présentation.
