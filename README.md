# ShoppingWebsite

A Persian, right-to-left multi-seller marketplace for Iran. Product prices are displayed in toman.

## Project status

Planning is approved. Milestone 1 specification and Milestone 2 foundation are in progress. No milestone has passed its completion checks yet.

See [the detailed milestone plan](docs/MILESTONES.md) for scope, order, dependencies, and completion checks.

## Release scope

The first release covers the buyer journey from product discovery through delivery or refund, with usable seller and administrator portals. Payment support is designed for a conventional online card gateway and provider adapters for Tara, SnappPay, and DigiPay, subject to merchant approval and each provider's current integration contract. Loyalty, subscriptions, ads, and advanced logistics follow the first release.

## Development stack

The initial Docker Compose stack has five services: Django API, PostgreSQL, Redis, Celery worker, and a separate frontend placeholder. The placeholder confirms the service boundary; the real responsive frontend remains to be built. See [the architecture decision](docs/product/ARCHITECTURE.md) and [product requirements](docs/product/REQUIREMENTS.md).

To start locally, copy `.env.example` to `.env`, replace both placeholder secrets, then run `docker compose up --build`. The frontend is at `http://localhost:3000`, the Django health endpoint at `http://localhost:8000/health/`, and the Django admin at `http://localhost:8000/admin/`. Django admin is currently a framework bootstrap, not the full custom administrator panel in Milestone 3. Docker Engine must be running. The stack has not yet been executed end to end on this workstation because its Docker daemon is unavailable.
