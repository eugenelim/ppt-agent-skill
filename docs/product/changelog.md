# Changelog

All notable user-visible changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> Maintenance: this file is updated in the same PR that introduces the
> change. CI will warn (configurable: block) when a PR touches code that
> changes user-visible behavior but does not touch this file.
>
> Entries can be drafted from conventional commits: `git log --oneline`
> filtered to `feat:` and `fix:` since the last tag is a starting point,
> not a finished product. Rewrite for users, not contributors. See the
> [Common Changelog guidance](https://common-changelog.org/) — the audience
> is humans who use the software, not humans who wrote it.

## [Unreleased]

### Added

- (nothing yet)

### Changed

- English is now the primary README. `README.md` is the English edition and the
  Chinese edition moved to `README_ZH.md`; each links to the other. Bookmarks
  pointing at the old `README_EN.md` will no longer resolve.

### Deprecated

- (nothing yet)

### Removed

- (nothing yet)

### Fixed

- The chart count shown in both READMEs is now 20 everywhere. The hero badge
  and architecture table still said 18 after stacked bar and treemap were
  added, and the English and Chinese file trees disagreed with each other.
- The `Architecture` link in each README's top navigation now scrolls to the
  right section instead of doing nothing.
- Both README file trees now show the logo, banner and hero images under
  `docs/assets/`, which is where they actually live.

### Security

- (nothing yet)
