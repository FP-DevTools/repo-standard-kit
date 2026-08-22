<Describe how and where this repo ships: package registry, container image,
deployment target, and what triggers a release (tag push, manual dispatch,
merge to `main`, etc.). Include rollback steps if non-obvious.>

- Cut releases from `main` with tags: `git tag vX.Y.Z && git push --tags`.
- `<CI/CD pipeline name and what it does on tag push>`
