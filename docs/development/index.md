# Development

The project separates reusable benchmark logic from experiment tracking and
command-line orchestration. Start with the [architecture](architecture.md), then
use the [extension guide](extending.md) for a small change.

Keep changes on a feature branch until review. Preserve saved notebook outputs
unless the change requires replacing them. Do not commit generated results,
credentials, data volumes, or local environments.

Before proposing a change, run the relevant [tests](testing.md) and build the
[documentation](documentation.md). Describe changes to query semantics explicitly.
