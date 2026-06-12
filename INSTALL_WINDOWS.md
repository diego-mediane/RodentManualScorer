# Installation Guide — Windows

This guide will take you from a fresh Windows PC to a working installation of **Rodent Manual Scorer**, even if you have never used Python before. Follow every step in order.

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
2. Click **Download** — it will detect that you are on Windows automatically.
3. Open the downloaded `.exe` installer.
4. When asked about installation type, choose **"Just Me"** (recommended).
5. On the **Advanced Options** screen, tick **"Add Anaconda3 to my PATH environment variable"**.
   > This makes it possible to run Anaconda commands from the Anaconda Prompt.
6. Complete the installation with all other defaults.

---

## Step 2 — Open the Anaconda Prompt

1. Press the **Windows key** and type `Anaconda Prompt`.
2. Click **Anaconda Prompt** (not PowerShell) from the search results.
3. A black command window will open. This is where you will type all the commands below.

> **Tip:** Copy each command, right-click inside the Anaconda Prompt window to paste, and press `Enter` to run it.

---

## Step 3 — Create a dedicated environment

```bash
conda create -n rms python=3.11 -y
```

This creates a new isolated environment called `rms`. It may take a minute or two.

---

## Step 4 — Activate the environment

```bash
conda activate rms
```

You will see `(rms)` appear at the start of your prompt. **You must do this every time you open a new Anaconda Prompt before running the tool.**

---

## Step 5 — Install the required packages

Run these two commands one at a time, waiting for each to finish:

```bash
conda install -c conda-forge pyqt -y
```

```bash
pip install opencv-python-headless numpy pandas openpyxl xlsxwriter
```

---

## Step 6 — Download the tool

1. Go to: **https://github.com/diego-mediane/RodentManualScorer**
2. Click the green **Code** button → **Download ZIP**
3. Open your **Downloads** folder, right-click the ZIP file, and select **Extract All**.
4. Move the extracted folder somewhere easy to find, such as your **Desktop** or **Documents** folder.

---

## Step 7 — Run the tool

1. In the Anaconda Prompt, navigate to the folder you extracted. For example, if it is on your Desktop:

```bash
cd C:\Users\YourUsername\Desktop\RodentManualScorer
```

Replace `YourUsername` with your actual Windows username.

2. Make sure your environment is active (you should see `(rms)` — if not, run `conda activate rms` first).

3. Run the tool:

```bash
python VideoTimerWindows.py
```

The application window should open. You are ready to score.

---

## Running the tool next time

Every time you want to use the tool, open **Anaconda Prompt** and run:

```bash
conda activate rms
cd C:\Users\YourUsername\Desktop\RodentManualScorer
python VideoTimerWindows.py
```

---

## Troubleshooting

**"conda is not recognised as a command"**
Close the Anaconda Prompt, reopen it, and try again. If the problem persists, reinstall Anaconda and make sure you tick *"Add Anaconda3 to my PATH environment variable"* during setup.

**"No module named PyQt5" or similar error**
Make sure you see `(rms)` in your prompt before running the script. If not, run `conda activate rms` first.

**The video loads but the screen stays black**
Try converting your video to `.mp4` (H.264). Some `.avi` or `.mov` codecs are not supported by the default Windows video backend. You can use [VLC](https://www.videolan.org/) or [HandBrake](https://handbrake.fr/) (both free) to convert.

**The app asks me to enter FPS manually**
Some video files do not store their frame rate. Check the video properties (right-click the file → Properties → Details tab) and enter the correct FPS value when prompted.

**The window title bar shows an error about Microsoft Visual C++**
Install the [Microsoft Visual C++ Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist) (x64 version) and restart your computer.

**Antivirus blocks the script from running**
This is a false positive. Add an exception for the `RodentManualScorer` folder in your antivirus settings, or temporarily disable real-time protection while running the tool.

---

## Updating

To get a new version of the tool, download the latest ZIP from GitHub and replace the old files. Your saved CSV data will not be affected.

To update the Python packages:

```bash
conda activate rms
pip install --upgrade opencv-python-headless numpy pandas openpyxl xlsxwriter
```
