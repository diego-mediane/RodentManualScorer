# Installation Guide — macOS

This guide will take you from a fresh Mac to a working installation of **Rodent Manual Scorer**, even if you have never used Python before. Follow every step in order.

---

## What you will install

| Software | Purpose |
|---|---|
| Anaconda | Manages Python and all required packages |
| Python 3.11 | The programming language the tool runs on |
| PyQt5, OpenCV, NumPy, pandas, openpyxl | Libraries the tool depends on |

---

## Step 1 — Install Anaconda

1. Open your browser and go to: **https://www.anaconda.com/download**
2. Click **Download** — it will detect that you are on a Mac automatically.
   - If you have an **Apple Silicon Mac** (M1/M2/M3/M4 chip), choose the **Apple Silicon** installer.
   - If you have an **older Intel Mac**, choose the **Intel** installer. (Not sure? Click the Apple menu → *About This Mac*.)
3. Open the downloaded `.pkg` file and follow the installer prompts. Accept all defaults.
4. When installation is complete, open **Launchpad** (the rocket icon in your Dock) and search for **Anaconda Navigator** to confirm it installed correctly.

---

## Step 2 — Open the Anaconda Prompt (Terminal)

1. Open **Launchpad** and search for **Terminal**, or open **Finder → Applications → Utilities → Terminal**.
2. You will see a window with a command prompt. This is where you will type the commands below.

> **Tip:** Copy each command exactly as written, paste it into the Terminal with `Cmd+V`, and press `Enter` to run it.

---

## Step 3 — Create a dedicated environment

It is best practice to keep Rodent Manual Scorer in its own isolated environment so it does not interfere with other Python projects.

```bash
conda create -n rms python=3.11 -y
```

This creates a new environment called `rms` running Python 3.11. It may take a minute.

---

## Step 4 — Activate the environment

```bash
conda activate rms
```

You will see `(rms)` appear at the start of your prompt. **You must do this every time you open a new Terminal before running the tool.**

---

## Step 5 — Install the required packages

Run these two commands one at a time:

```bash
conda install -c conda-forge pyqt -y
```

```bash
pip install opencv-python numpy pandas openpyxl xlsxwriter
```

Wait for each command to finish before running the next.

---

## Step 6 — Download the tool

1. Go to: **https://github.com/diego-mediane/RodentManualScorer**
2. Click the green **Code** button → **Download ZIP**
3. Open your **Downloads** folder and double-click the ZIP file to extract it.
4. Move the extracted folder somewhere easy to find, such as your **Desktop** or **Documents** folder.

---

## Step 7 — Run the tool

1. In Terminal, navigate to the folder you just extracted. For example, if you put it on your Desktop:

```bash
cd ~/Desktop/RodentManualScorer
```

2. Make sure your environment is active (you should see `(rms)` in the prompt — if not, run `conda activate rms` first).

3. Run the tool:

```bash
python VideoTimer.py
```

The application window should open. You are ready to score.

---

## Troubleshooting

**"conda: command not found"**
Close Terminal completely, reopen it, and try again. If the problem persists, reinstall Anaconda and tick the box that says *"Add to PATH"* during installation.

**"No module named PyQt5" or similar**
Make sure you activated the environment (`conda activate rms`) before running the script.

**The video loads but shows a black screen**
Try a different video format. `.mp4` files encoded with H.264 work most reliably on macOS.

**The app asks me to enter FPS manually**
Some video files do not store their frame rate. Check the video's properties (right-click → Get Info) and enter the correct FPS when prompted.

**Permission denied when running the script**
Run `chmod +x VideoTimer.py` in Terminal and try again.

---

## Updating

To get a new version of the tool, download the latest ZIP from GitHub and replace the old files. Your data (CSV files) will not be affected.

To update the Python packages:

```bash
conda activate rms
pip install --upgrade opencv-python numpy pandas openpyxl xlsxwriter
```
