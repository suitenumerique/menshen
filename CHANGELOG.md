# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a
Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

#### Dependencies

- Upgrade `django-ninja` to `1.7.1`

### Fixed

- Restore alternate password hashers list to automatically upgrade users' hash
- Support client secrets containing percent sequences (see
  [Django-Ninja #1780](https://github.com/vitalik/django-ninja/pull/1780))

## [v0.3.0] - 2026-09-17

### Added

- Implement service provider credentials automated generation, encryption and
  validation

### Changed

- Remove `--app` flag in the container production command
- Remove unused OIDC authentication backend

### Fixed

- Allow bearer or mac introspected token types

### Removed

- Clean unused `django-cors-headers` configured dependency

## [v0.2.0] - 2026-07-29

### Changed

- Remove enums `Enum` suffix
- Switch from DRF to Django-Ninja API framework

#### Dependencies

- Upgrade `django` to `6.0.7`
- Upgrade `django-lasuite` to `0.0.27`
- Upgrade `drf-spectacular` to `0.30.0`
- Upgrade `sentry-sdk` to `2.66.1`
- Upgrade `uvicorn` to `0.51.0`

## [v0.1.0] - 2026-07-14

### Added

- Implement base Token Exchange (RFC 8693) endpoints

[unreleased]: https://github.com/suitenumerique/menshen/compare/v0.3.0...HEAD
[v0.3.0]: https://github.com/suitenumerique/menshen/releases/v0.3.0
[v0.2.0]: https://github.com/suitenumerique/menshen/releases/v0.2.0
[v0.1.0]: https://github.com/suitenumerique/menshen/releases/v0.1.0
