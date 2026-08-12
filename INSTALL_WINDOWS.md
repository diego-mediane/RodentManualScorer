# Rodent Manual Scorer — Windows installation

This guide is written for users who do not normally use Python.

## What you need

- Windows 10 or Windows 11
- Internet access for the initial installation
- The Rodent Manual Scorer repository downloaded from GitHub
- Python 3.11 in an isolated environment

The Windows script is:

`VideoTimerWindows.py`

## 1. Download the project

On the GitHub repository page:

1. Click **Code**
2. Click **Download ZIP**
3. Open the downloaded ZIP
4. Extract the folder somewhere easy to find, for example your Desktop

GitHub may call the extracted folder `RodentManualScorer-main`. That is normal.

## 2. Install Miniconda

Download and install Miniconda for Windows from the official Anaconda/Miniconda website.

During installation, use the normal recommended options.

You do **not** need to add Anaconda/Miniconda manually to the Windows PATH.

After installation, open **Anaconda Prompt** or **Miniconda Prompt** from the Start menu.

## 3. Create a clean Python 3.11 environment

In Anaconda Prompt/Miniconda Prompt, run:

```bash
conda create -n rms python=3.11 pip -y
```

Then activate it:

```bash
conda activate rms
```

You should now see `(rms)` near the start of the command line.

You normally only create this environment once.

## 4. Go to the Rodent Manual Scorer folder

In File Explorer:

1. Open the extracted RodentManualScorer folder
2. Click the address bar
3. Copy the full folder path

Then in Anaconda Prompt type:

```bash
cd /d "PASTE-YOUR-FOLDER-PATH-HERE"
```

For example:

```bash
cd /d "C:\Users\YourName\Desktop\RodentManualScorer-main"
```

## 5. Install the required packages

With `(rms)` active and the prompt inside the project folder, run:

```bash
python -m pip install -r requirements.txt
```

Wait until installation finishes.

## 6. Start Rodent Manual Scorer

Run:

```bash
python VideoTimerWindows.py
```

The application window should open.

## Every time you want to use it later

Open Anaconda Prompt or Miniconda Prompt and run:

```bash
conda activate rms
```

Go to the RodentManualScorer folder:

```bash
cd /d "C:\path\to\RodentManualScorer-main"
```

Then run:

```bash
python VideoTimerWindows.py
```

## Supported video files

The scorer accepts:

- `.mp4`
- `.avi`
- `.mov`
- `.mkv`

The filename extension does not guarantee that Windows/OpenCV can decode the codec stored inside the file.

If one recording does not open:

1. Test a known-good `.mp4`
2. If that works, convert a copy of the problematic video to a standard H.264 `.mp4`
3. Keep the original recording unchanged

## Windows security or antivirus warning

Only use files downloaded from the official RodentManualScorer GitHub repository.

If Windows Security or another antivirus product flags a file:

1. Do not disable real-time protection
2. Confirm the file came from the official repository
3. Scan the downloaded file/folder
4. If it is still flagged unexpectedly, open a GitHub issue and include the exact detection name

A security warning should not automatically be assumed to be a false positive.

## Updating Rodent Manual Scorer

If you downloaded the project as a ZIP:

1. Download the newest ZIP from GitHub
2. Extract it into a new folder
3. Keep your scoring output files separately
4. Activate the same `rms` environment
5. Run the newest `VideoTimerWindows.py`

If `requirements.txt` has changed, run again:

```bash
python -m pip install -r requirements.txt
```

## Troubleshooting

### `conda` is not recognised

Use **Anaconda Prompt** or **Miniconda Prompt** rather than a normal Command Prompt.

### `ModuleNotFoundError`

Make sure `(rms)` is visible, then run:

```bash
python -m pip install -r requirements.txt
```

### The application does not open

From the project folder, run:

```bash
python VideoTimerWindows.py
```

Copy the complete error shown in the prompt when opening a GitHub issue.

### A video does not open or playback is unusual

Try a standard H.264 `.mp4`.

Rodent Manual Scorer includes Windows-specific video-backend handling, but codec support still depends on the video and the OpenCV/FFmpeg build installed with Python.

### Excel export fails

Make sure the environment is active, then reinstall the requirements:

```bash
python -m pip install -r requirements.txt
```

## Getting help

If the problem persists, open an issue on the RodentManualScorer GitHub repository and include:

- Windows version
- Python version shown by `python --version`
- full error text
- video extension and, if known, codec
- whether the problem occurs with more than one video
