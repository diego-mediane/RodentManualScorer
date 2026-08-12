# Rodent Manual Scorer — macOS installation

This guide is written for users who do not normally use Python.

## What you need

- macOS
- Internet access for the initial installation
- The Rodent Manual Scorer repository downloaded from GitHub
- Python 3.11 in an isolated environment

The macOS script is:

`VideoTimer.py`

## 1. Download the project

On the GitHub repository page:

1. Click **Code**
2. Click **Download ZIP**
3. Open the downloaded ZIP
4. Move the extracted folder somewhere easy to find, for example your Desktop

GitHub may call the extracted folder `RodentManualScorer-main`. That is normal.

## 2. Install Miniconda

Download and install Miniconda for macOS from the official Anaconda/Miniconda website.

Choose the installer that matches your Mac:

- **Apple silicon** for M1/M2/M3/M4 and newer Apple chips
- **Intel** for older Intel Macs

After installation, open **Terminal**.

## 3. Create a clean Python 3.11 environment

In Terminal, run:

```bash
conda create -n rms python=3.11 pip -y
```

Then activate it:

```bash
conda activate rms
```

You should now see `(rms)` near the start of the Terminal line.

You normally only create this environment once.

## 4. Go to the Rodent Manual Scorer folder

The easiest method is:

1. Type `cd ` in Terminal, including the space
2. Drag the extracted RodentManualScorer folder from Finder into the Terminal window
3. Press **Return**

For example:

```bash
cd /Users/yourname/Desktop/RodentManualScorer-main
```

## 5. Install the required packages

With `(rms)` active and Terminal inside the project folder, run:

```bash
python -m pip install -r requirements.txt
```

Wait until installation finishes.

## 6. Start Rodent Manual Scorer

Run:

```bash
python VideoTimer.py
```

The application window should open.

## Every time you want to use it later

Open Terminal and run:

```bash
conda activate rms
```

Then move into the RodentManualScorer folder and run:

```bash
python VideoTimer.py
```

## Supported video files

The scorer accepts:

- `.mp4`
- `.avi`
- `.mov`
- `.mkv`

Whether a particular file opens also depends on the codec used inside that video. If one video does not open, try converting a copy to a standard H.264 `.mp4` while keeping the original recording unchanged.

## macOS security message

If macOS blocks the script because it was downloaded from the internet, first confirm that you downloaded the files from the official RodentManualScorer GitHub repository.

You may then need to allow the application/script in **System Settings → Privacy & Security**.

Do not disable macOS security protections globally.

## Updating Rodent Manual Scorer

If you downloaded the project as a ZIP:

1. Download the newest ZIP from GitHub
2. Extract it into a new folder
3. Keep your old scoring output files separately
4. Activate the same `rms` environment
5. Run the newest `VideoTimer.py`

If `requirements.txt` has changed, run again:

```bash
python -m pip install -r requirements.txt
```

## Troubleshooting

### `conda: command not found`

Close Terminal and reopen it after installing Miniconda.

### `ModuleNotFoundError`

Make sure `(rms)` is visible in Terminal, then run:

```bash
python -m pip install -r requirements.txt
```

### The window does not open

From the project folder, run:

```bash
python VideoTimer.py
```

Read the error shown in Terminal and include that text when opening a GitHub issue.

### A video will not open

Try another known-good `.mp4` first. If that works, the problem is probably the codec of the original video rather than the scorer itself.

## Getting help

If the problem persists, open an issue on the RodentManualScorer GitHub repository and include:

- your macOS version
- whether the Mac is Apple silicon or Intel
- the Python version shown by `python --version`
- the full Terminal error
- the video extension and, if known, codec
