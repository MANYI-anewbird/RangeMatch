# Diligence Search Agent

Status: IMPLEMENTED_V0_1

Live gate: `PASSED` on 2026-08-08 using bounded OpenAI web search and approved public sources.

## Purpose

Search current public sources for buyer-diligence context that is not a
canonical F01–F08 parcel measurement. The agent helps answer what public rules,
guidance, drought notices, or protected-land constraints deserve follow-up.

## Authority

The search agent may:

- search current public government and university-extension sources;
- summarize sources in plain language;
- preserve URL, title, retrieval time, and jurisdiction scope;
- mark missing or conflicting public evidence for follow-up.

It may not:

- write or change F01–F08 Land Facts;
- change Engine decisions, Factor signals, or operation ranking;
- infer parcel boundaries, legal access, water rights, permit certainty,
  usable livestock water, forage condition, carrying capacity, or profitability;
- treat a search snippet as proof that a rule applies to the parcel.

## V0.1 topics

- REGULATION_AND_PERMITS
- LOCAL_AG_GUIDANCE
- CURRENT_DROUGHT
- PUBLIC_LAND_CONSTRAINTS

## Source gate

V0.1 accepts HTTPS sources on U.S. government or educational domains only.
Search results are DILIGENCE_CONTEXT_ONLY. State/county applicability must
still be reviewed; absence of a result is not clearance.

Jurisdiction scope is taken from confirmed parcel metadata (county/state) when available. A street address is not sent to the search model as a fallback. If jurisdiction is unresolved, the result is visibly downgraded to `United States (national screen only)` and must not dominate the buyer report.

Sources are canonicalized and deduplicated before display. Tracking parameters do not create separate evidence records. Each buyer-visible item must state what it means, what to do next, and that parcel applicability is not yet confirmed.

## Runtime

- FIXTURE: deterministic, offline, test-only evidence package.
- OPENAI: Responses API with the web_search tool, source inclusion, and
  approved-domain filtering.
- Missing credentials or transport failure fails closed.

The result is stored beside the investigation as a diligence side branch. It
is not merged into the Engine input or MatchResult.

The UI runs this Agent after deterministic evaluation, shows it in progress as `Public Diligence Agent`, and renders current guidance separately from parcel facts.
