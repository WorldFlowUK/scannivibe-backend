# Metaworld Map Backend Alignment Plan

## Goal
Align backend contracts with the frontend metaworld map roadmap so 3D activity rendering, engagement loops, and telemetry are production-safe.

## Priority Backlog (Mirrored from Frontend Needs)
1. Wire CTA continuity by guaranteeing route-ready payloads for:
- venue details
- check-in navigation context
- local hub quick actions
2. Remove mock-dependent frontend paths by exposing real activity metrics:
- vibe score source
- energy level source
- trending/social proof source
3. Type telemetry payloads consistently across API and client.
4. Standardize API error envelopes to eliminate ad-hoc frontend parsing.

## API Contract Extensions (Phase 2/3 Support)
1. Heatmap point enrichment:
- `live_count: int`
- `trend_delta: float`
- `confidence: float` (0..1)
- `updated_at: ISO8601`
2. Venue 3D metadata:
- `geometry` (polygon/multipolygon or centroid fallback)
- `height_m` (nullable)
- `category_theme` (string enum)
3. Privacy/aggregation guards:
- `is_aggregated: bool`
- `suppressed_reason: string | null`

## Endpoint Work Items
1. `GET /heatmap`
- Accept time windows: `now`, `15m`, `1h`, `24h`.
- Return normalized activity and confidence fields.
- Include server-side freshness metadata (`generated_at`).
2. `GET /locations/:id`
- Return map-ready fields needed to replace mock score/energy data.
3. `GET /locations`
- Include lightweight trend/social-proof summary fields for feed cards.
4. Optional (phase 3):
- `GET /recommendations/next-best`
- `GET /missions/daily`

## Error Contract Standardization
1. Use consistent error shape for all endpoints:
```json
{
  "error": {
    "code": "STRING_CODE",
    "message": "Human readable",
    "details": {}
  },
  "request_id": "uuid"
}
```
2. Keep HTTP semantics strict (`4xx` client, `5xx` server, `429` rate limit).
3. Include `request_id` for correlation with frontend telemetry.

## Telemetry Contract Requirements
1. Required events:
- `heatmap_fetch_success`
- `heatmap_fetch_error`
- `heatmap_render_complete` (frontend emits, backend correlates by request_id)
- funnel chain: `map_view -> venue_focus -> detail_open -> navigate -> checkin_success`
2. Add backend logs/metrics labels:
- `filter_key`
- `time_window`
- `response_size`
- `latency_ms`
- `request_id`

## Performance and Reliability Gates
1. P95 `GET /heatmap` latency target:
- <= 300 ms cached
- <= 800 ms uncached
2. Cache strategy:
- key by normalized filters + time window
- short TTL for live windows
3. Query guardrails:
- cap max points per response
- enforce minimum aggregation thresholds for privacy
4. Add circuit/fallback behavior on data source degradation.

## GitHub Rollout Instructions (Backend Repo)
1. Push branch:
```bash
git checkout feature/metaworld-map-roadmap
git push -u origin feature/metaworld-map-roadmap
```
2. Open PR:
- `https://github.com/WorldFlowUK/scannivibe-backend/compare/main...feature/metaworld-map-roadmap`
3. PR title suggestion:
- `docs: align backend contracts with metaworld map roadmap`
4. In PR description include:
- link to frontend PR
- contract changes list
- rollout/rollback notes

## Merge Sequence
1. Merge frontend docs PR and backend docs PR together.
2. Finalize contract fields before frontend Phase 2 implementation.
3. Start endpoint implementation behind feature flags and progressive rollout.
