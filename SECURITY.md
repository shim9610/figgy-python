# Security policy

## Supported versions

Security fixes target the latest published figgyplot release and current
development on `main`; older development commits are not maintained as release
branches. As of 2026-10-16, PyPI has 0.2.1 and this source tree prepares 0.3.0.
See [distribution status](docs/DISTRIBUTION.md) for platform coverage.

## Report a vulnerability privately

Email **ssy9610@gmail.com**. When GitHub private vulnerability reporting is
enabled, you can also use [Security → Report a vulnerability](https://github.com/shim9610/figgy-python/security/advisories/new).

Include the affected commit/version, operating system, Python version,
native/browser backend, a minimal reproduction, and the expected security impact.
Remove credentials and private datasets. Do not publish exploit details, tokens
or private reports in public issues or pull requests.

The maintainer reviews reports on a best-effort basis; there is no guaranteed
response deadline or paid support agreement. We will coordinate a fix and
disclosure with the reporter. Renderer issues may need coordination with
[shim9610/figgy](https://github.com/shim9610/figgy).

## Runtime boundaries

Native inputs allocate CPU/GPU resources directly. Resource exhaustion from a
large requested plot is possible; automatic downsampling, streaming and eviction
are not part of the API. Notebook rendering uses a separate browser GPU and an
initial binary transfer. A timeout, crash or renderer validation failure can be
reported as a normal bug; use private reporting if it exposes a security impact.

Only run Python code and notebook content you trust. Copy Python exports should
be reviewed before execution. Generated upstream JS/WASM assets must retain their
recorded hashes; do not bypass integrity checks to resolve a packaging failure.

