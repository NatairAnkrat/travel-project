# API contract

This documents the API **as it's actually implemented today** (post `auth-service`/`group-service`/`travel-service`/`search-service`/`recommendation-service`/`edit-service` split), for whoever builds the frontend against it.

## Topology

There is no API gateway. The frontend must know about **three separate base URLs**, each an independent OpenShift Route:

| Service | Exposed? | Route | Spec |
|---|---|---|---|
| `auth-service` (Java) | yes, public | `infra/k8s/auth-service/route.yaml` | [`auth-service.yaml`](./auth-service.yaml) |
| `group-service` (Java) | yes, public | `infra/k8s/group-service/route.yaml` | [`group-service.yaml`](./group-service.yaml) |
| `travel-service` (Java) | yes, public | `infra/k8s/travel-service/route.yaml` | [`travel-service.yaml`](./travel-service.yaml) |
| `search-service` (Python/FastAPI) | no — internal only | — | reached via `travel-service` `/api/v1/search/*`, which proxies verbatim |
| `recommendation-service` (Python/FastAPI) | no — internal only | — | called by `travel-service` (`POST /travels`) and by `edit-service`; never called directly by the frontend |
| `edit-service` (Python/FastAPI) | no — internal only | — | reached via `travel-service` `/api/v1/travels/{id}/edit`, which proxies verbatim |

All three Java services read `frontend.origin` / `FRONTEND_ORIGIN` (default `http://localhost:5173`, i.e. Vite) for CORS — the frontend origin needs to be set consistently across all three deployments, not just one.

## Known gap: no token verification outside auth-service

`auth-service` issues a JWT access token + rotating refresh token (`POST /auth/login`), but **`group-service` and `travel-service` have no JWT filter at all** — every endpoint that needs to know "who is calling" takes it as a plain body field instead (`created_by`, `requested_by`, `user_id`). Nothing currently verifies that field against the caller's actual token, so any client can act as any user id today. Before wiring up a real frontend this needs:

- A shared JWT verification filter/interceptor added to `group-service` and `travel-service` (they already share the same secret/issuer via `auth-service`'s `JwtService` — that logic needs to be extracted somewhere both can use, e.g. a shared library or gateway).
- Those services' controllers changed to derive the acting user from the verified token instead of trusting the request body for it. The request/response shapes in the specs below still show `created_by` etc. as body fields because that's what's actually deployed right now — treat that as the thing to fix, not the target contract.

## Async job pattern

`POST /travels` (travel-service) and `POST /travels/{id}/edit` (proxied to edit-service) both return `202` with a `job_id` immediately — itinerary generation runs in the background via Claude tool-use and can take minutes. The frontend needs to poll:

- `GET /travels/generation/{jobId}` (travel-service, for a fresh travel)
- `GET /edits/{jobId}` (travel-service, proxied to edit-service, for an edit)

There's no push/webhook/SSE — polling is the only option as implemented.
