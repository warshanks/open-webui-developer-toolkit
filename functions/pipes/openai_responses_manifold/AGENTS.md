# Pipeline Instructions for OpenAI Responses Manifold

This guide applies to all files in this directory.

## Versioning

`openai_responses_manifold.py` contains a `version:` field in its top level docstring.
We follow **Semantic Versioning** (`MAJOR.MINOR.PATCH`):

- **MAJOR** – incompatible or breaking changes.
- **MINOR** – backward compatible feature additions.
- **PATCH** – bug fixes or internal changes that keep existing behaviour.

## Changelog Updates

Whenever `openai_responses_manifold.py` is modified, increment the version field
following the rules above **and** add an entry to `CHANGELOG.md` under a new
heading `## [x.y.z] - YYYY-MM-DD` describing the change.

Documentation-only edits do not require a version bump.

## Code Style and Testing

Run `pre-commit` before committing changes. This executes **ruff** and the
pipeline's unit tests to ensure style and importability remain intact.

## README

If you add new valves or features, update the features table in `README.md` so
documentation stays in sync with the source file. Each feature row has a
`Last updated` column showing when that row's status or notes last changed.
Update that date whenever you modify a feature so we know exactly when each
capability was most recently reviewed.
