# Rodent Manual Scorer

**A free, open-source desktop tool for manual behavioural video scoring.**

Developed by Diego Hassan Mediane

---

## What is it?

Rodent Manual Scorer is a Python-based application that lets researchers score behaviours in video recordings frame-by-frame, in real time. You assign keyboard keys to behaviours (e.g. `G` for *Grooming*, `F` for *Freezing*), play the video, and hold down the corresponding key whenever that behaviour occurs. The tool records start time, end time, and duration for every event, and exports everything to CSV or Excel.

It is designed to be simple enough for complete beginners while being precise enough for rigorous research.

---

## Features

- 🎬 **Video playback** — supports `.mp4`, `.avi`, `.mov`, `.mkv`
- ⌨️ **Custom key-to-behaviour mapping** — assign any key to any behaviour
- ⏱️ **Automatic timing** — millisecond-accurate start/end/duration recording
- 🔢 **Multiple phases** — split a session into named experimental phases (e.g. Baseline, Treatment)
- 📊 **Timeline visualisation** — see all scored events overlaid on a progress bar
- ↩️ **Undo / Redo** — `Ctrl+Z` / `Ctrl+Y`
- 💾 **Autosave** — saves a recovery CSV every 5 minutes automatically
- 📁 **Export** — save results as CSV or Excel (with Summary + Detailed sheets)
- 🐛 **Drag & drop** — drag a video file directly onto the window
- 🟢 **Live scoring panel** — the active behaviour lights up while you hold its key, with a running timer
- 🗂️ **Multiple sessions** — score the same video several times and keep every pass; start fresh or continue a copy
- 💬 **Tooltips everywhere** — hover any control for a short explanation
- 📘 **Built-in tutorial** — press `F1` or click the Tutorial button for a step-by-step guide

---

## Which script should I use?

| Your computer | Script to use |
|---|---|
| **macOS** | `VideoTimer.py` |
| **Windows** | `VideoTimerWindows.py` |

The two scripts are functionally identical. The Windows version includes additional fixes for Windows-specific video backend quirks.

---

## Quick Start

1. Follow the installation guide for your OS:
   - 📄 [Installation — macOS](INSTALL_MAC.md)
   - 📄 [Installation — Windows](INSTALL_WINDOWS.md)
2. Read the [Tutorial](TUTORIAL.md) to learn how to score your first video.

---

## Staying Informed
- ⭐ **Star this repository** — lets us see how many people are using the tool

---

## Citation

**Citation is mandatory** for any published academic work that uses this software or data produced with it. GitHub also provides a **"Cite this repository"** button (top-right of this page) which generates ready-to-use citations in APA, BibTeX, and other formats automatically.

**APA format:**
> Mediane, D. H. (2025). *Rodent Manual Scorer* [Software]. Anastasiades Lab & Cahill Lab. https://github.com/diego-mediane/RodentManualScorer

**BibTeX:**
```bibtex
@software{mediane2025rms,
  author       = {Mediane, Diego Hassan},
  title        = {Rodent Manual Scorer},
  year         = {2025},
  url          = {https://github.com/diego-mediane/RodentManualScorer},
  institution  = {Anastasiades Lab \& Cahill Lab},
  note         = {Software for manual behavioural video scoring}
}
```

---

## License

This software is released under a **Non-Commercial Academic Licence** — see [LICENSE](LICENSE) for full terms.

In short:
- ✅ Free to use for academic and non-commercial research
- ✅ Free to share and modify for non-commercial purposes
- ❌ **You may not sell or commercialise this software**
- 📄 **Citation is required** in any published work

---

## Contact

For questions, bug reports, or feature requests, please open an **Issue** on this repository.
