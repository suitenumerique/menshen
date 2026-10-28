# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a
Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Add `TokenExchangeClient.close()` method and allow to use the client as a
  context manager to close its HTTP connections
- Add `TokenExchangeAsyncClient`, an asynchronous version of the
  `TokenExchangeClient`

### Changed

- Migrate `TokenExchangeClient` from `requests` to `httpx2`. This is a
  breaking change: API errors now raise `httpx2.HTTPStatusError` and request
  timeouts raise `httpx2.TimeoutException` (instead of `requests` exceptions).
  Note that `httpx2` relies on the system certificate store (via `truststore`)
  instead of `certifi` to verify TLS certificates.

#### Dependencies

- Replace `requests` by `httpx2`

## [v0.2.0] - 2026-10-12

### Added

- Add `requests_timeout` parameter to `Configuration` used as the default value
  for every API request

## [v0.1.0] - 2026-09-21

### Added

- Add base Menshen API client

[Unreleased]: https://github.com/suitenumerique/menshen/compare/v0.2.0-client...HEAD
[v0.2.0]: https://github.com/suitenumerique/menshen/releases/v0.2.0-client
[v0.1.0]: https://github.com/suitenumerique/menshen/releases/v0.1.0-client
