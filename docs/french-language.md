# French input and investor output

The investor workflow normalizes language once before screening, allocation,
risk, simulation, evidence and compliance. These stages continue to consume
the existing typed contract (`ticker` and integer `add_pct`, or `exclude`);
they do not individually translate user messages or call a model for arithmetic.

`domain/request_language.py` normalizes Unicode accents, case and apostrophes,
recognizes common French/English operations and explicit quantities in `%`,
`pour cent` or `points de pourcentage`. French number words from zero to one
hundred are recognized; the engine still accepts only whole changes from 1 to
100 points. Zero, decimals, monetary amounts and unsupported number forms
require clarification. No rounding or guessed amount is introduced.

Examples:

| Request | Normalized instruction |
| --- | --- |
| « Ajoutez TD.TO de cinq points » | `{"ticker":"TD.TO","add_pct":5}` |
| « Réduisez TD.TO de deux pour cent » | `{"ticker":"TD.TO","add_pct":-2}` |
| « Retirer TD.TO » | `{"exclude":"TD.TO"}` |
| « Ajouter TD.TO à cinq pour cent » | Clarify target versus variation |
| « N’ajoute pas TD.TO 5 % » | Clarify; no edit |

Percent quantities here describe percentage-point variations, as in the existing
API, rather than relative changes or target weights. The response states this
convention. Asset names and tickers must match the supplied catalogue, ignoring
case and accents. An unknown dotted symbol is never shortened to a known one.
Only a quantity-only reply may borrow the asset and direction from the last user
turn; assistant messages cannot supply them.

When explicit positive or negative phrasing has an asset and a valid quantity but
no recognized operation, `application/request_interpretation.py` can use the
existing `LLMClient` once. Its JSON response may select only `add`, `reduce` or
`clarify`, with a verbatim supporting quote. It cannot return a ticker, amount,
weights, constraints or prose for display. Extra/duplicate fields, malformed
JSON, invented quotes, uncertain intent, model errors and insufficient deadline
budget produce clarification. Negations, conditions, targets, multi-edit
instructions and conflicting recognized actions are rejected before this call.
There is no model retry or separate deployment. This interpretation call is
recorded under `llm_calls` with stage `interpret_request`; explanation retains its
existing, separate bounded repair budget. Live model interpretation remains a
semantic judgment, not a guarantee of perfect language understanding.

Without a configured model, deterministic French parsing remains available and
unrecognized phrasing asks for clarification. Existing bootstrap model settings
control availability; no new AWS resources or credentials are required.

French investor summaries, observations, disclaimers, error messages, portfolio
names and public evidence descriptions use checked templates and label mappings.
Technical field names, status codes, asset names and the original private audit
bundle remain unchanged. This does not translate the legacy explicit-profile
technical API or arbitrary externally supplied text. Data, mathematical results,
allocation policy, evidence checks and explicit confirmation remain authoritative.

Offline verification: `python -m pytest backend/tests/test_request_language.py`.
Tests cover French/English equivalence, accents, number words, ambiguity, unknown
symbols, direction across turns, model output validation, deadlines, outages and
the orchestrated path through the existing numerical and release gates.
