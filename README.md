# Text‑to‑Mic (Open‑Source Edition)

This repository provides a simple, open‑source alternative to **Text‑to‑Mic** – an AI‑powered tool that converts text into speech and plays it through both your speakers/headphones and a virtual microphone feed.  The goal of this project is to mirror the core functionality described in [Andrew Ward’s Text‑to‑Mic application](https://www.scorchsoft.com/blog/text-to-mic-for-meetings/), while remaining completely open source and avoiding any proprietary dependencies.

Developed by: Kieran Spencer

Check me out @ https://workflais.rf.gd/

## Features

- **Text‑to‑Speech (TTS)** using OpenAI’s high quality voices (Alloy, Echo, Fable, Onyx, Nova and Shimmer) when an API key is supplied.  If no API key is provided, the program falls back to your system’s built‑in voices via the `pyttsx3` library.  The OpenAI API provides lifelike audio with multiple voices and supports real‑time streaming【123381020912997†L59-L80】.
- **Dual output**: the generated audio is played simultaneously to two output devices – typically your headphones and a virtual microphone.  A virtual microphone can be created using a tool such as **VB‑Cable** (a virtual audio driver that forwards audio from its playback side to its recording side【752540102179021†L24-L27】).  The program lets you select which devices to use via simple drop‑downs.  Under the hood it uses the `python‑sounddevice` library, which allows selecting specific output devices by index【568831489183316†L180-L187】.
- **Speech‑to‑Text‑to‑Speech (STTTS)**: record your voice with a single click, transcribe it locally using the open‑source [Whisper](https://github.com/openai/whisper) model (Whisper is a general‑purpose speech recognition model trained on a large, diverse audio dataset【553031916526482†L118-L124】), optionally tidy up the transcript with the built‑in grammar checker, and then speak the result back through the selected devices.
- **Automatic copyediting**: using the `language_tool_python` wrapper around LanguageTool – an open‑source grammar and style checker【315745988103700†L84-L87】 – the text can be automatically cleaned up before it’s spoken.  This helps remove typos or minor grammatical mistakes from your typed or recorded input.
- **Single hotkey**: the **Enter** key acts as a global trigger when the application has focus, immediately speaking whatever is in the text box to both outputs.  This mirrors the streamlined behaviour of the original application, which advertises hotkey control for quick operation【123381020912997†L75-L80】.

## Installation

1. **Install dependencies.**  The project uses Python 3.9 or newer.  From the repository root run:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   pip install -r requirements.txt
   ```

   The dependencies include:

   - `sounddevice`: plays and records audio and allows choosing output devices【568831489183316†L180-L187】.
   - `numpy` and `scipy`: handle audio arrays and reading/writing WAV files.
   - `openai`: calls the OpenAI speech API for high‑quality voices.
   - `pyttsx3`: fallback TTS engine if no API key is provided.
   - `whisper`: performs speech‑to‑text.  Whisper is open source and capable of multilingual transcription【553031916526482†L118-L124】.
   - `language_tool_python`: provides offline grammar and spell‑checking【315745988103700†L84-L87】.
   - `keyboard`: captures the Enter key as a hotkey.
   - `tkinter`: Python’s built‑in GUI toolkit for the user interface.

2. **Install a virtual audio device (optional).**  To feed audio into an online meeting as if you were speaking, you need a virtual microphone.  On Windows, one popular option is **VB‑Cable**, a virtual audio device where all audio sent to its playback input is forwarded to its recording output【752540102179021†L24-L27】.  Download and install VB‑Cable from [vb‑audio.com](https://vb-audio.com/Cable/).  After installation you will see a new “Cable Input” and “Cable Output” device in your system’s sound settings.

3. **Run the application.**

   ```bash
   python text_to_mic_tool/main.py
   ```

4. **Provide your OpenAI API key (optional).**  Without a key the application will fall back to your system’s built‑in voices via `pyttsx3`.  To use OpenAI’s voices you must set the `OPENAI_API_KEY` environment variable or paste your key into the settings dialog accessed through the GUI.

## Usage

When you launch the application you’ll see a simple window with:

1. **Text box** – type what you want spoken here.  Press **Enter** or click **Speak** to generate speech.  If copy‑editing is enabled, the text is first passed through LanguageTool to remove typos or minor grammar mistakes.
2. **Voice selection** – choose from the available OpenAI voices (Alloy, Echo, Fable, Onyx, Nova, Shimmer【950377366767914†L423-L430】) or default system voices when using the fallback engine.
3. **Output device selectors** – choose which audio devices should receive the output.  Usually you’ll pick your headphones for monitoring and your virtual microphone (e.g. VB‑Cable) for sending audio into a meeting.
4. **Record button** – click **Record** to capture a few seconds of speech from your microphone.  The recording is transcribed using the open‑source Whisper model【553031916526482†L118-L124】, optionally copy‑edited, and then spoken through the selected devices.  This replicates the STTTS functionality described in the original tool【123381020912997†L72-L75】.
5. **Copy‑edit checkbox** – toggles automatic grammar checking using LanguageTool【315745988103700†L84-L87】.

Once your devices are configured and your API key (if any) is set, simply type or record your message and press **Enter**.  The app will generate speech and route it to both outputs.  If using a virtual microphone, select it as the microphone in your meeting software (e.g. Teams, Zoom) to make the AI voice audible to other participants【123381020912997†L153-L161】.

## Note on Latency

The Whisper transcription and OpenAI speech synthesis operate on your local machine and the internet, respectively.  Speech‑to‑text and text‑to‑speech may each introduce a few seconds of delay, depending on hardware and network conditions.  The fallback `pyttsx3` voice is offline and responds instantly but offers lower quality.  For the lowest latency, use shorter input phrases and consider pre‑generating frequently used phrases.

## License

This project is distributed under the GNU General Public License v3.0 license.  Please review the license file for details.
