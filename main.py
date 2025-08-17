#!/usr/bin/env python3
"""
Simple open‑source implementation of Text‑to‑Mic for Windows.

This application provides a graphical interface to convert typed or recorded
speech into audible output that is simultaneously sent to two audio devices:
typically your headphones and a virtual microphone (such as VB‑Cable).  When an
OpenAI API key is supplied, it uses OpenAI’s high quality voices; otherwise it
falls back to the local text‑to‑speech engine via `pyttsx3`.  The speech can
also be copy‑edited using LanguageTool before playback, and the STTTS feature
records a short clip from your microphone, transcribes it with Whisper and then
speaks the result.

To run the application:

    python main.py

Ensure you have installed the dependencies in requirements.txt and, if
performing speech‑to‑text, that ffmpeg is present on your system.

"""

import io
import os
import sys
import threading
import queue
import json
from dataclasses import dataclass, field
from typing import Optional, Tuple, List

import numpy as np
import sounddevice as sd
from scipy.io import wavfile

# Attempt to import optional dependencies.  The application will still run
# without them, but functionality will be limited.
try:
    import openai
except ImportError:
    openai = None

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

try:
    import whisper
except Exception:
    # Catch all exceptions when importing whisper.  Some environments (e.g.
    # Windows without a C library) may raise non‑ImportError exceptions during
    # import.  In such cases we disable the STTTS functionality by setting
    # whisper to None and allow the rest of the application to run.
    whisper = None

try:
    import language_tool_python
except ImportError:
    language_tool_python = None

import tkinter as tk
from tkinter import ttk, messagebox, filedialog


CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')


@dataclass
class AppConfig:
    """Holds configuration for output devices and API settings."""
    headphone_device: Optional[int] = None
    mic_device: Optional[int] = None
    voice: str = 'alloy'
    api_key: Optional[str] = None
    sample_rate: int = 24000  # default sample rate for OpenAI TTS

    def load(self, path: str = CONFIG_FILE):
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for field_name in ['headphone_device', 'mic_device', 'voice', 'api_key', 'sample_rate']:
                    if field_name in data:
                        setattr(self, field_name, data[field_name])
            except Exception as exc:
                print(f"Failed to load config: {exc}")

    def save(self, path: str = CONFIG_FILE):
        data = {
            'headphone_device': self.headphone_device,
            'mic_device': self.mic_device,
            'voice': self.voice,
            'api_key': self.api_key,
            'sample_rate': self.sample_rate,
        }
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as exc:
            print(f"Failed to save config: {exc}")


class TextToMicApp(tk.Tk):
    def __init__(self, config: AppConfig):
        super().__init__()
        self.title("Text‑to‑Mic (Open Source)")
        self.geometry("600x400")
        self.config = config
        self.playback_queue: "queue.Queue[Tuple[int, np.ndarray]]" = queue.Queue()
        self._stop_event = threading.Event()
        self.whisper_model = None
        self.language_tool = None
        self._init_gui()
        self._init_audio_thread()
        # Load Whisper and LanguageTool asynchronously to avoid blocking the UI
        threading.Thread(target=self._load_optional_models, daemon=True).start()

    def _init_gui(self):
        # Top frame for text entry
        top_frame = ttk.Frame(self)
        top_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.text_box = tk.Text(top_frame, wrap=tk.WORD, height=8)
        self.text_box.pack(fill=tk.BOTH, expand=True)
        self.text_box.bind('<Return>', self._on_enter_key)

        # Options frame for controls and settings
        options_frame = ttk.Frame(self)
        options_frame.pack(fill=tk.X, padx=10, pady=5)

        # Voice selection
        ttk.Label(options_frame, text="Voice:").pack(side=tk.LEFT, padx=(0, 5))
        self.voice_var = tk.StringVar(value=self.config.voice)
        voices = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']
        self.voice_combo = ttk.Combobox(options_frame, textvariable=self.voice_var, values=voices, state='readonly', width=10)
        self.voice_combo.pack(side=tk.LEFT)

        # Copy edit checkbox
        self.copy_edit_var = tk.BooleanVar(value=False)
        copy_chk = ttk.Checkbutton(options_frame, text="Copy‑edit", variable=self.copy_edit_var)
        copy_chk.pack(side=tk.LEFT, padx=10)

        # Buttons
        speak_btn = ttk.Button(options_frame, text="Speak (Enter)", command=self._speak)
        speak_btn.pack(side=tk.LEFT, padx=5)
        record_btn = ttk.Button(options_frame, text="Record", command=self._record)
        record_btn.pack(side=tk.LEFT, padx=5)
        settings_btn = ttk.Button(options_frame, text="Settings", command=self._open_settings)
        settings_btn.pack(side=tk.LEFT, padx=5)

        # Status label
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_label.pack(fill=tk.X, side=tk.BOTTOM)

    def _init_audio_thread(self):
        # Thread that continuously plays audio from the queue
        def playback_worker():
            while not self._stop_event.is_set():
                try:
                    fs, data = self.playback_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                self._play_audio_to_devices(fs, data)
        self.playback_thread = threading.Thread(target=playback_worker, daemon=True)
        self.playback_thread.start()

    def _load_optional_models(self):
        """Load Whisper and LanguageTool in the background."""
        if whisper is not None:
            try:
                self.status_var.set("Loading Whisper model…")
                # Use tiny model for lower resource usage
                self.whisper_model = whisper.load_model('tiny')
            except Exception as exc:
                print(f"Failed to load Whisper model: {exc}")
        if language_tool_python is not None:
            try:
                self.status_var.set("Starting LanguageTool…")
                self.language_tool = language_tool_python.LanguageTool('en-US')
            except Exception as exc:
                print(f"Failed to start LanguageTool: {exc}")
        self.status_var.set("Ready")

    def _on_enter_key(self, event: tk.Event):
        # Prevent newline insertion
        self._speak()
        return 'break'

    # ---------------------- Core Functions ----------------------
    def _speak(self):
        """Generate speech from the text box and queue it for playback."""
        text = self.text_box.get("1.0", tk.END).strip()
        if not text:
            return
        if self.copy_edit_var.get() and self.language_tool:
            # Copy edit with LanguageTool
            try:
                matches = self.language_tool.check(text)
                text = language_tool_python.utils.correct(text, matches)
            except Exception as exc:
                print(f"Copyedit failed: {exc}")
        threading.Thread(target=self._generate_and_queue_audio, args=(text,), daemon=True).start()

    def _generate_and_queue_audio(self, text: str):
        """Generate audio from text (using OpenAI or pyttsx3) and put it in the queue."""
        self.status_var.set("Generating speech…")
        try:
            fs, data = self._tts_to_audio(text)
            self.playback_queue.put((fs, data))
            self.status_var.set("Playback queued")
        except Exception as exc:
            self.status_var.set("Error during TTS")
            messagebox.showerror("Error", f"Failed to generate speech: {exc}")

    def _record(self):
        """Record audio from the default microphone, transcribe it and speak it."""
        if not whisper:
            messagebox.showerror("Missing dependency", "Whisper is not installed. Please install the 'whisper' package.")
            return
        # Ask for duration
        duration = 5  # seconds
        sample_rate = 16000
        self.status_var.set("Recording…")
        try:
            recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='float32')
            sd.wait()
            # Save to a temporary buffer
            wav_bytes = io.BytesIO()
            wavfile.write(wav_bytes, sample_rate, recording)
            wav_bytes.seek(0)
            # Transcribe
            self.status_var.set("Transcribing…")
            result = self.whisper_model.transcribe(wav_bytes)
            text = result.get('text', '').strip()
            if self.copy_edit_var.get() and self.language_tool:
                matches = self.language_tool.check(text)
                text = language_tool_python.utils.correct(text, matches)
            # Insert the text into the text box and speak it
            self.text_box.delete("1.0", tk.END)
            self.text_box.insert(tk.END, text)
            self.status_var.set("Transcribed. Generating speech…")
            self._generate_and_queue_audio(text)
        except Exception as exc:
            self.status_var.set("Error during recording")
            messagebox.showerror("Error", f"Recording/transcription failed: {exc}")

    def _tts_to_audio(self, text: str) -> Tuple[int, np.ndarray]:
        """Convert text to audio (sample_rate, numpy array) using OpenAI or pyttsx3."""
        # Prefer OpenAI if API key and library available
        if self.config.api_key and openai is not None:
            openai.api_key = self.config.api_key
            try:
                # Request wav output from OpenAI (response_format='wav')
                response = openai.audio.speech.create(
                    model="tts-1",
                    voice=self.voice_var.get(),
                    input=text,
                    response_format='wav'
                )
                audio_bytes = response.content
                wav_io = io.BytesIO(audio_bytes)
                fs, data = wavfile.read(wav_io)
                # Convert to float32 in range [-1, 1]
                if data.dtype == np.int16:
                    data = data.astype(np.float32) / 32768.0
                elif data.dtype == np.int32:
                    data = data.astype(np.float32) / 2147483648.0
                elif data.dtype == np.uint8:
                    data = (data.astype(np.float32) - 128) / 128.0
                else:
                    data = data.astype(np.float32)
                return fs, data
            except Exception as exc:
                print(f"OpenAI TTS failed: {exc}")
                # Fallback to pyttsx3
        # Fallback TTS with pyttsx3
        if pyttsx3 is None:
            raise RuntimeError("pyttsx3 is not installed and no valid OpenAI key available.")
        engine = pyttsx3.init()
        # Attempt to set voice if present in system voices
        selected_voice = self.voice_var.get().lower()
        for voice in engine.getProperty('voices'):
            if selected_voice in voice.id.lower() or selected_voice in voice.name.lower():
                engine.setProperty('voice', voice.id)
                break
        # Save to temporary file
        tmp_path = os.path.join(os.path.dirname(__file__), 'tmp_output.wav')
        engine.save_to_file(text, tmp_path)
        engine.runAndWait()
        fs, data = wavfile.read(tmp_path)
        os.remove(tmp_path)
        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32768.0
        elif data.dtype == np.int32:
            data = data.astype(np.float32) / 2147483648.0
        elif data.dtype == np.uint8:
            data = (data.astype(np.float32) - 128) / 128.0
        else:
            data = data.astype(np.float32)
        return fs, data

    def _play_audio_to_devices(self, fs: int, data: np.ndarray):
        """Play audio data to both selected output devices."""
        # data is shape (samples,) or (samples, channels)
        # If mono, convert to stereo for both outputs
        if data.ndim == 1:
            data = np.repeat(data[:, None], 2, axis=1)
        # Determine devices
        devices = []
        if self.config.headphone_device is not None:
            devices.append(self.config.headphone_device)
        if self.config.mic_device is not None:
            devices.append(self.config.mic_device)
        if not devices:
            # Play on default device
            sd.play(data, fs)
            sd.wait()
            return
        # Play on each device sequentially using non‑blocking playback
        threads = []
        for device_id in devices:
            # Each playback in separate thread to avoid blocking UI
            def play_on_device(device=device_id):
                try:
                    sd.play(data, fs, device=device)
                    sd.wait()
                except Exception as exc:
                    print(f"Playback error on device {device}: {exc}")
            t = threading.Thread(target=play_on_device, daemon=True)
            t.start()
            threads.append(t)
        # Wait for all threads to finish
        for t in threads:
            t.join()

    def _open_settings(self):
        """Open a dialog for selecting devices and API key."""
        dialog = tk.Toplevel(self)
        dialog.title("Settings")

        # Device list retrieval
        device_list = sd.query_devices()

        def device_name(index):
            return f"{index}: {device_list[index]['name']}" if 0 <= index < len(device_list) else "None"

        # Headphones dropdown
        ttk.Label(dialog, text="Headphones device:").grid(row=0, column=0, sticky=tk.W, pady=5)
        headphone_var = tk.StringVar(value=device_name(self.config.headphone_device) if self.config.headphone_device is not None else "None")
        headphone_options = ["None"] + [device_name(i) for i in range(len(device_list))]
        headphone_combo = ttk.Combobox(dialog, textvariable=headphone_var, values=headphone_options, state='readonly', width=40)
        headphone_combo.grid(row=0, column=1, padx=5, pady=5)

        # Mic dropdown
        ttk.Label(dialog, text="Virtual mic device:").grid(row=1, column=0, sticky=tk.W, pady=5)
        mic_var = tk.StringVar(value=device_name(self.config.mic_device) if self.config.mic_device is not None else "None")
        mic_options = ["None"] + [device_name(i) for i in range(len(device_list))]
        mic_combo = ttk.Combobox(dialog, textvariable=mic_var, values=mic_options, state='readonly', width=40)
        mic_combo.grid(row=1, column=1, padx=5, pady=5)

        # API key entry
        ttk.Label(dialog, text="OpenAI API Key:").grid(row=2, column=0, sticky=tk.W, pady=5)
        api_var = tk.StringVar(value=self.config.api_key if self.config.api_key else "")
        api_entry = ttk.Entry(dialog, textvariable=api_var, show='*', width=40)
        api_entry.grid(row=2, column=1, padx=5, pady=5)

        def save_settings():
            # Parse headphone
            def parse_device(s):
                if s == "None":
                    return None
                try:
                    idx = int(s.split(':')[0])
                    return idx
                except Exception:
                    return None
            self.config.headphone_device = parse_device(headphone_var.get())
            self.config.mic_device = parse_device(mic_var.get())
            self.config.api_key = api_var.get().strip() or None
            self.config.voice = self.voice_var.get()
            self.config.save()
            dialog.destroy()
            messagebox.showinfo("Settings", "Settings saved.")
        save_btn = ttk.Button(dialog, text="Save", command=save_settings)
        save_btn.grid(row=3, column=0, columnspan=2, pady=10)

    def on_close(self):
        self._stop_event.set()
        self.config.save()
        self.destroy()


def main():
    config = AppConfig()
    config.load()
    app = TextToMicApp(config)
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()


if __name__ == '__main__':
    main()