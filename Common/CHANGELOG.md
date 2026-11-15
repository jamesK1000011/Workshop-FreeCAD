# Changelog

All notable changes to Workshop Common. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

The first tagged release, 0.4.0 (the version in `package.xml`), is being
prepared. It is the last one.

### Removed

- The shared Workshop workbench and its tests: each Workshop add-on now has
  its own workbench. This release registers nothing, says once at start
  that it is no longer needed, and can be removed.

### Added

- Release preparation: a README, complete Addon Manager metadata with its
  own `LICENSE`, licence entries checked for every file, and this changelog.
