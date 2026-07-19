from __future__ import annotations

"""Factual call summaries.

The agent's own `finish_demo` summary is preferred. When a call ends before the
agent confirms the objective (early hangup, silence, carrier drop), this builds a
truthful structural summary instead. It intentionally contains no verbatim
transcript, so the MCP result stays a summary and never leaks raw call content.
"""


def fallback_summary(
    *,
    language: str,
    disclosure_delivered: bool,
    user_turns: int,
) -> str:
    fr = language == "fr"
    if user_turns <= 0:
        if fr:
            return "Appel connecté ; aucune réponse audible de la personne."
        return "Call connected; no audible response from the person."
    if fr:
        opening = (
            "L'annonce a été diffusée et la" if disclosure_delivered else "La"
        )
        return (
            f"{opening} personne a échangé ({user_turns} prise(s) de parole), "
            "puis l'appel s'est terminé."
        )
    opening = (
        "The disclosure was played and the" if disclosure_delivered else "The"
    )
    return f"{opening} person spoke ({user_turns} turn(s)); the call then ended."
