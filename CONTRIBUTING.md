# Contributing

Thanks for helping with VentWise.

## How We Work

- Check the existing GitHub issues before starting any new work.
- If `dev` is behind `main`, sync `dev` with `main` before creating a task branch.
- Create a short-lived branch from `dev` for each task.
- Keep each branch focused on one issue or one tightly related change.
- Open a pull request into `dev` when the task is ready.
- After merge, close the related issue and delete the branch.
- If a release or mainline update is requested, merge `dev` into `main` after the task lands on `dev`.

## Issues

- Track every TODO as a GitHub issue.
- Keep each issue small, specific, and minimal.
- Read existing open and recent closed issues before opening a new one.
- Use this structure:
  - `Goal`
  - `Scope`
  - `Acceptance`
- Tag the issue and assign it to `@AlexSantini10`.
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
