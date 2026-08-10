# RangeMatch Buyer Dashboard — Design QA

- Source visual truth: `/Users/hongmanyi/.codex/generated_images/019fdcf4-0560-7600-a315-51623ae17849/exec-45e934cb-9c05-4513-8ac3-21091c6dbcac.png`
- Browser implementation: `http://127.0.0.1:5174/investigations/inv_794228486dd6409a`
- Final desktop capture: `/Users/hongmanyi/RangeMatch/web/screenshots/33-buyer-dashboard-live-konza-final.png`
- Final mobile capture: `/Users/hongmanyi/RangeMatch/web/screenshots/35-buyer-dashboard-mobile-viewport.png`
- Desktop viewport: 1488 × 1026 CSS px, device scale factor 1
- Source pixels: 1488 × 1026
- Implementation pixels: 1488 × 1026
- Mobile viewport/capture: 390 × 844 CSS/pixels, device scale factor 1
- State: completed live Konza investigation, `PARTIAL`, validated buyer narrative available after deterministic dashboard rendering

## Full-view comparison evidence

The final implementation preserves the selected concept's two-column buyer dashboard, large parcel map, parcel acreage callout, climate/season strip, vegetation and water summaries, operation comparison, evidence confidence, diligence actions, and core report actions. The implementation intentionally replaces the mock's unsupported directional fit labels with Engine-bound `Evidence incomplete` states and does not invent a suitability score.

The implementation uses the existing token-free OSM/MapLibre basemap rather than the aspirational satellite composite shown in the source. This is an intentional runtime constraint; the parcel polygon, acreage, water/road context, and data-verification framing remain visible. A satellite basemap can be added later through the existing map-style configuration without changing the dashboard contract.

## Focused region comparison evidence

- Operation panel: Cow-Calf and Sheep remain peers; both show the authoritative HOLD-equivalent copy and explicitly state that no directional fit score is approved.
- Evidence confidence: displayed separately from operation fit and capped at `Moderate` while any Factor is `NEEDS_VERIFICATION` or `UNKNOWN`.
- Climate and seasonal region: annual precipitation is shown as a measured Land Fact; all four seasonal cells say `Seasonal series not collected` because no seasonal series exists.
- Diligence actions: long registry language is translated into three concise buyer actions while the full technical text remains in the report/appendix.
- Mobile viewport: no horizontal overflow (`clientWidth == scrollWidth == 390`); map callouts, climate strip, and badges remain legible.

## Comparison history

### Iteration 1

- [P1] Parcel map appeared unavailable until the LLM buyer narrative finished.
  - Fix: separated parcel-resolution and deterministic-report loading from the slower LLM request in `InvestigationPage.tsx`.
  - Post-fix evidence: the confirmed parcel map renders before narrative completion.
- [P2] Evidence confidence displayed `High` despite material verification gaps.
  - Fix: capped confidence at `Moderate` when any Factor is `NEEDS_VERIFICATION` or `UNKNOWN`.
- [P2] Diligence rows exposed long technical registry sentences.
  - Fix: added deterministic buyer-readable action labels while keeping detailed evidence below.
- [P2] Desktop vertical rhythm clipped core actions below the reference viewport.
  - Fix: tightened dashboard-only header spacing, right-column gaps, row padding, and action padding.
- [P2] Cow icon was reused for Sheep.
  - Fix: replaced the duplicate animal glyph with a distinct, honest Sheep initial until a licensed sheep icon asset is added.

### Iteration 2

Post-fix desktop and mobile captures show no remaining actionable P0/P1/P2 mismatch. The remaining differences are intentional product constraints or P3 polish:

- [P3] OSM basemap is less visually rich than the source satellite composite.
- [P3] Sheep uses a typographic initial rather than a bespoke animal silhouette.

## Required fidelity surfaces

- Typography: Fraunces display face and Figtree body hierarchy match the agrarian editorial direction; no clipping or broken wraps observed.
- Spacing/layout: desktop composition and above-the-fold action stack now fit the 1488 × 1026 target; mobile is single-column without horizontal overflow.
- Colors/tokens: cream paper, deep green, pale vegetation green, muted amber HOLD state, and verification styling are consistent with the source.
- Image quality: MapLibre renders sharply; the basemap difference is documented as an intentional no-paid-token constraint.
- Copy/content: buyer-facing summary language is concise; scientific limitations and unknowns remain available in the report and appendix.
- Interaction/accessibility: links and map controls are semantic, progress and status have accessible labels, and no console errors were observed.

## Primary interactions tested

- Confirmed parcel map rendering
- Progress-to-terminal transition
- Early deterministic dashboard rendering while LLM narrative is pending
- Validated narrative/fallback behavior
- Report, comparison, and appendix anchor actions
- Desktop and mobile responsive layouts

## Implementation checklist

- [x] Selected concept 1 implemented
- [x] Real parcel-bound investigation rendered
- [x] Missing seasonal data shown honestly
- [x] Fit and evidence confidence separated
- [x] No invented fit score or species ranking
- [x] Desktop/mobile screenshots captured
- [x] Browser console checked (no warnings/errors)
- [x] Frontend tests and production build passed

final result: passed
