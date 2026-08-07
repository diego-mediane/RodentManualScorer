# Changelog

All notable changes to this project are documented here.
The format is based on Keep a Changelog, and the project aims to follow semantic versioning.

## [2.0.1] - 2026-08-07

### Fixed
- Finalises a behaviour held when the video reaches the end, using the video duration as the bout end time so the event appears in the timeline, history, CSV and Excel output.
- Finalises active bouts safely before pause, stop, timeline seeking, phase changes and session changes.
- Prevents held-key state from leaking into a newly loaded video and resets scoring sessions whenever a video is loaded, preventing events from one recording carrying into another.
- Corrects modified-key handling and key release when modifier keys are released in a different order.
- Prevents application shortcuts such as save, load, undo and redo from being assigned as behaviour keys.
- Corrects CSV quoting on macOS for behaviour or phase names containing commas or quotation marks.
- Clears stale undo/redo state and rebuilds event state when loading a scoring CSV.


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
- The legacy scripts were retained in this release and were removed in version 2.0.1.

## [1.0.0]

### Added
- Initial release: video playback, key-to-behaviour mapping, millisecond timing, phases, timeline, undo and redo, autosave, and CSV and Excel export.
