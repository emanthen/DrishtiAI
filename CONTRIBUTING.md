# Contributing to DrishtiAI

## Commit style

Conventional Commits. One logical change per commit.

```
feat(api): add plate search endpoint
fix(pipeline): handle dropped frames in analog ingest
chore(deps): update paddleocr to 2.8.1
docs(installer): add analog capture card FFmpeg commands
```

Types: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `perf`, `ci`.

## Branch naming

```
feat/phase-1-plate-read
fix/analog-capture-ffmpeg-args
chore/update-deps
```

## Pull request checklist

- [ ] `make lint` passes
- [ ] `make typecheck` passes
- [ ] `make test` passes
- [ ] No new AGPL/GPL dependency in prod path (`make licenses` clean)
- [ ] Phase acceptance criteria met (if closing a phase)
- [ ] `CHANGELOG.md` updated

## License hygiene

Every new dependency must be checked before merging. Run `make licenses` and inspect output. If a dependency is AGPL or GPL, it must be removed, replaced, or explicitly approved with an isolation strategy documented in `LICENSES.md`.

## Secrets

Never commit `.env` files, credentials, certificates, or model weights. If you accidentally commit a secret, rotate it immediately and contact the team.
