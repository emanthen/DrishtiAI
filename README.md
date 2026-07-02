# DrishtiAI

On-premises ANPR and video analytics platform for South Asian markets.

Turns every camera on your site into a vehicle sensor — reading plates, logging vehicles, opening gates, and surfacing incidents — with all data stored on your premises.

## Quick start (development)

```bash
# Prerequisites: Docker, Docker Compose, Node.js 20+, pnpm 9+, uv, Python 3.12+
make install
make dev
```

Services will be available at:
- Web dashboard: http://localhost:3000
- API: http://localhost:8000
- Admin panel: http://localhost:8001/admin
- MinIO console: http://localhost:9001

## Documentation

- [Architecture](docs/architecture.md)
- [Installer guide](docs/installer-guide.md)
- [Admin guide](docs/admin-guide.md)
- [Guard quick reference](docs/guard-guide.md)
- [API reference](docs/api-reference.md)

## Repository layout

```
apps/          Service applications (api, admin, worker, pipeline, web, mobile)
packages/      Shared libraries (shared-python, shared-ts, ui)
ml/            ML model training, fine-tuning, benchmarks
deploy/        Docker Compose configs, install scripts, migration bundles
docs/          End-user and integrator documentation
```

## License

Proprietary. See [LICENSES.md](LICENSES.md) for third-party dependency licenses.
