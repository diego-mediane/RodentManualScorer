# Tutorial — How to Score a Video

This tutorial walks you through a complete scoring session from start to finish. By the end, you will have a CSV file with timestamped behavioural events ready for analysis.

The example used here scores a rodent video for three behaviours: **Grooming**, **Freezing**, and **Rearing**. The exact behaviours and keys are fully customisable — use whatever fits your experiment.

---

## Overview of the workflow

```
Load video → Assign keys → Play & score → Save results
```

---

## Part 1 — Opening the application

**macOS:**
```bash
conda activate rms
cd ~/Desktop/RodentManualScorer
python VideoTimer.py
```

**Windows (Anaconda Prompt):**
```bash
conda activate rms
cd C:\Users\YourUsername\Desktop\RodentManualScorer
python VideoTimerWindows.py
```

The main window opens with a black video area on the left and a panel of controls on the right.

---

## Part 2 — Loading a video

You can load a video in two ways:

**Option A — Menu:**
Go to **File → Load Video** (or press `Ctrl+O`), then navigate to your video file and click Open.

**Option B — Drag and drop:**
Drag your video file directly onto the black video area.

Supported formats: `.mp4`, `.avi`, `.mov`, `.mkv`

Once loaded, the timeline bar and timestamp display will update to show the video's total duration. The video does not play automatically.

> **If a dialog asks you to enter FPS manually:** your video file does not store its frame rate. Enter the correct value (commonly `25` for PAL recordings or `30` for NTSC). You can check this by right-clicking your video file → Properties (Windows) or Get Info (Mac).

---

## Part 3 — Assigning keys to behaviours

Before scoring, you must tell the software which key corresponds to which behaviour.

1. Click the **Assign Keys** button on the right panel.
2. The *Assign Keys and Behaviours* dialog opens.
3. Type a behaviour name in the text box — for example: `Grooming`
4. Click **Add & Assign**.
5. The status message changes to: *"Assigning for 'Grooming'. Press any key now..."*
6. Press the key you want to use — for example: `G`
7. The behaviour appears in the table with its assigned key.
8. Repeat for each behaviour:
   - `Freezing` → `F`
   - `Rearing` → `R`
   - ... and so on

**Other actions in this dialog:**

| Button | What it does |
|---|---|
| Reassign Key | Change the key for a selected behaviour |
| Clear Key | Remove the key assignment (behaviour stays) |
| Rename | Rename a behaviour |
| Remove | Delete a behaviour entirely |

9. Click **OK** when done.

The right panel now shows each behaviour, its key, total time recorded, and event count — all starting at zero.

> **Your key assignments are saved automatically** between sessions. You do not need to reassign them every time you open the software.

---

## Part 4 — Setting up phases (optional)

If your experiment has distinct phases (e.g. *Baseline* and *Drug Treatment*), you can track them separately.

1. Click **Start New Phase**.
2. Type the phase name (e.g. `Baseline`) and click OK.
3. Choose a colour for this phase in the colour picker — this colour will appear in the timeline bar.
4. All events scored after this point will be labelled under this phase.

To start a new phase during playback, press the **`P`** key.

If you do not use phases, all events are automatically labelled as *Default Phase*.

---

## Part 5 — Scoring behaviours

1. Click **Play** (or press `Space`).
2. The video begins playing at normal speed.
3. **To score a behaviour:** hold down its assigned key for as long as the behaviour is occurring.
   - The key down = behaviour **start**
   - The key up = behaviour **end**
   - The duration is calculated automatically
4. The behaviour label on the right panel highlights in green while a key is held.
5. The timeline bar updates in real time to show scored intervals.

**Example session:**
- At 00:00:05, the animal begins grooming → hold `G`
- At 00:00:08, grooming stops → release `G` — a 3-second grooming event is recorded
- At 00:00:12, the animal freezes → hold `F`
- At 00:00:19, freezing stops → release `F` — a 7-second freezing event is recorded

**You can score multiple behaviours simultaneously** by holding multiple keys at once.

---

## Part 6 — Playback controls

| Control | Action |
|---|---|
| **Play** button / `Space` | Play or resume |
| **Pause** button / `Space` | Pause (remembers position) |
| **Stop** button | Stop and return to start |
| Slider | Scrub to any point in the video |
| Speed dropdown | Change playback speed (0.1× to 8×) |
| `F11` | Toggle fullscreen |

> **Tip for slow behaviours:** Use 0.5× or 0.25× speed to catch fast or subtle behaviours with better precision. The scoring keys still work at all speeds.

> **Tip for review:** You can scrub through the video after scoring to visually check the timeline.

---

## Part 7 — Undoing a mistake

Pressed the wrong key, or held it too long?

- Press `Ctrl+Z` (or go to **Edit → Undo Last**) to remove the most recent event.
- The video will rewind to the start of that event automatically.
- Press `Ctrl+Y` (or go to **Edit → Redo**) to reapply an undone event.

---

## Part 8 — Viewing a summary during scoring

At any point, go to **View → Show Time Spent** (or press `Ctrl+T`) to open a summary table showing:

- Total time spent on each behaviour
- Number of events (count)
- Percentage of total video time

This is useful for a quick mid-session check without stopping the video.

---

## Part 9 — Saving your results

When you are finished scoring, save your data. **Do this before closing the application.**

### Save as CSV

Go to **File → Save Scoring CSV** (or press `Ctrl+S`).

Choose a location and filename. The CSV will contain one row per event:

```
Phase,Behaviour,Start Time,End Time,Duration (s)
Default Phase,Grooming,00:00:05.000,00:00:08.000,3.000
Default Phase,Freezing,00:00:12.000,00:00:19.000,7.000
```

### Export as Excel

Go to **File → Export Excel** (or press `Ctrl+E`).

The Excel file contains two sheets:
- **Summary** — total time and event count per behaviour
- **Detailed_Events** — one row per event with full timestamps

---

## Part 10 — Loading a previous session

To resume scoring a video from a previously saved CSV:

1. Load the video as normal.
2. Go to **File → Load Scoring CSV** (or press `Ctrl+L`).
3. Select your saved CSV file.
4. All previous events are restored in the timeline and counts.

---

## Part 11 — Starting a new session

To clear all data and start fresh (keeping key assignments):

Go to **File → New Session** (or press `Ctrl+N`).

You will be asked to confirm. This clears all scored events and timers but does not affect saved files.

---

## Autosave

The tool automatically saves a recovery file called **`autosave_rms.csv`** every 5 minutes to the same folder as the script. If the application crashes, open this file to recover your data. It is overwritten each time, so treat your manual saves (Step 9) as your primary backup.

---

## Keyboard shortcuts — full reference

| Shortcut | Action |
|---|---|
| `Space` | Play / Pause |
| `Ctrl+O` | Load video |
| `Ctrl+S` | Save CSV |
| `Ctrl+E` | Export Excel |
| `Ctrl+L` | Load CSV |
| `Ctrl+N` | New session |
| `Ctrl+Z` | Undo last event |
| `Ctrl+Y` | Redo |
| `Ctrl+T` | Show time spent |
| `P` | Start new phase (during playback) |
| `F11` | Toggle fullscreen |
| Your assigned keys | Score behaviours (hold to record) |

---

## History panel

Go to **View → Show History** to open a floating panel that logs every action taken in the session (scored events, undos, phase changes). Useful for auditing your session.

---

## Tips for accurate scoring

- Do a dry run through the video before your first real scoring session to familiarise yourself with the behaviours.
- Use slow playback (0.5×) for fast or subtle behaviours, especially on the first pass.
- Score one behaviour type at a time across the full video if behaviours are hard to catch in real time, then combine the CSVs.
- Keep the application window in focus (click on it) before pressing scoring keys — if a text box or dialog is open, key presses go there instead.
