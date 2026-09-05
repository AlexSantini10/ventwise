# Contributing

Thanks for helping with VentWise.

## Start Here

1. Read the [README](README.md) and [documentation index](docs/INDEX.md).
2. Search existing [issues](https://github.com/AlexSantini10/ventwise/issues) before proposing work.
3. For code changes, set up the project with the [development guide](docs/development.md) and run `python -m pytest -q`.
4. Open an issue before starting a new feature, bug fix, or documentation task that is not already tracked.

## How We Work

- Check the existing GitHub issues before starting any new work.
- If `dev` is behind `main`, sync `dev` with `main` before creating a task branch.
- Create a short-lived branch from `dev` for each feature task.
- Keep each branch focused on one issue or one tightly related change.
- Open a pull request into `dev` when the task is ready.
- After merge, close the related issue and delete the branch.
- For finished feature work, also open and merge the requested `dev` to `main` pull request.

## Issues

- Track every TODO as a GitHub issue.
- Keep each issue small, specific, and minimal.
- Read existing open and recent closed issues before opening a new one.
- Use this structure:
  - `Goal`
  - `Scope`
  - `Acceptance`
- Tag the issue.
- Do not duplicate issues that already cover the same work.

## Branches

- Create the branch from `dev`, not from `main`.
- Use a short, descriptive branch name.
- Keep commits scoped to the task.
- Prefer one branch per issue.

## Pull Requests

- Open PRs into `dev`.
- Prefer small, reviewable PRs.
- Include tests when behavior changes.
- Update documentation when user-facing behavior changes.
- Link the related issue in the PR description.
- Mention any follow-up work explicitly.
- Use real Markdown line breaks in PR descriptions; do not render literal `\n` text.

### Suggested PR template

```md
## Goal
What this PR is trying to achieve.

## Scope
What changed and what stayed out of scope.

## Acceptance
- [ ] Relevant tests pass
- [ ] Documentation updated if needed
- [ ] Related issue linked

## Notes
Anything a reviewer should know.
```

## Versioning and Release Flow

- The contributor decides whether a version bump is needed as part of the task.
- Do not ask the maintainer for approval before applying a required bump.
- Use `patch` for fixes, `minor` for new features, and `major` for breaking changes or large version jumps.
- If the task is complete and a release is needed, bump the version first, then commit, then open the PR flow.
- After a task lands on `dev`, merge `dev` into `main` only when requested.

## Good Defaults

- Prefer clear, boring changes over broad refactors.
- Keep release notes and docs aligned with behavior changes.
- If a change affects Home Assistant behavior, include the relevant tests.
