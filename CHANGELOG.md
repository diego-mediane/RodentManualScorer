# Changelog

All notable changes to this project are documented here.
The format is based on Keep a Changelog, and the project aims to follow semantic versioning.

## [2.0.0] - 2026-06-12

### Added
- Live scoring panel on the right showing every behaviour, its key, running total and count, with the active behaviour highlighted and a live timer while its key is held.
- Multiple scoring sessions over the same video, with the choice to start a pass from scratch or continue a copy of a previous pass, and a dropdown to switch between sessions without losing any.
- Tooltips on every control, and a built-in tutorial available from the Help menu, the Tutorial button, or `F1`.

### Changed
- Reworked the interface theme so all text is readable across menus, dialogs, group boxes, checkboxes, dropdown popups and tooltips.

### Fixed
- Documentation and `requirements.txt` now use `opencv-python-headless` to avoid the Qt platform plugin conflict that could prevent the application from launching.

### Notes
- The previous release remains available as `VideoTimer_v1.py` and `VideoTimerWindows_v1.py`.

## [1.0.0]

### Added
- Initial release: video playback, key-to-behaviour mapping, millisecond timing, phases, timeline, undo and redo, autosave, and CSV and Excel export.
