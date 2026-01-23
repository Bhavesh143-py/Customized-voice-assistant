import tkinter as tk
from tkinter import ttk, scrolledtext
import sounddevice as sd
import threading
import queue
import numpy as np
from faster_whisper import WhisperModel

# Load Faster Whisper model
# Options: tiny, base, small, medium, large-v2, large-v3
# device options: "cpu", "cuda", "auto"
model = WhisperModel("base", device="cpu", compute_type="int8")

# Global variables
audio_queue = queue.Queue()
recording = False
audio_buffer = []
mic_dropdown = None
output_box = None
listening_label = None


# Get available microphones
def get_microphones():
    devices = sd.query_devices()
    return [dev["name"] for dev in devices if dev["max_input_channels"] > 0]


# Audio callback to collect audio chunks
def audio_callback(indata, frames, time, status):
    if status:
        print(status)
    audio_queue.put(indata.copy())


# Recording logic in a thread
def record_audio(device_index, output_widget, listening_label):
    global recording, audio_buffer

    # Show listening label
    listening_label.config(text="🎤 Listening...", fg="red")

    with sd.InputStream(
        samplerate=16000,
        blocksize=8000,
        device=device_index,
        dtype="float32",
        channels=1,
        callback=audio_callback,
    ):
        while recording:
            try:
                data = audio_queue.get(timeout=0.1)
                audio_buffer.append(data)

                # Process every 3 seconds of audio
                if len(audio_buffer) * 8000 / 16000 >= 3.0:
                    process_audio_chunk(output_widget)
            except queue.Empty:
                continue

    # Process remaining audio when stopped
    if len(audio_buffer) > 0:
        process_audio_chunk(output_widget)

    # Hide listening label
    listening_label.config(text="")


def process_audio_chunk(output_widget):
    global audio_buffer , callback_function ,final_text ,listening_label

    # Concatenate audio chunks
    audio_data = np.concatenate(audio_buffer, axis=0).flatten()
    audio_buffer = []

    # Transcribe with Faster Whisper
    segments, info = model.transcribe(audio_data, beam_size=5, language="en")
    final_text = ""
    # Display transcription
    for segment in segments:
        text = segment.text.strip()
        if text:
            output_widget.insert(tk.END, text + " ")
            output_widget.see(tk.END)
            final_text += text + " "

            if text.endswith(("?", "!")):
                stop_recording()
                listening_label.config(text="🧐 Processing...", fg="red")
                # 🔥 CALL THE CALLBACK INSTEAD OF returning
                if callback_function:
                    callback_function(final_text.strip())
                break


# Start recording button handler
def start_recording():
    global recording, mic_dropdown, output_box, listening_label
    if recording:
        return

    recording = True
    device_index = mic_dropdown.current()
    threading.Thread(
        target=record_audio,
        args=(device_index, output_box, listening_label),
        daemon=True,
    ).start()


# Stop recording button handler
def stop_recording():
    global recording
    recording = False


def show_recorder(on_final_text):
    global mic_dropdown, output_box, listening_label, callback_function
    
    callback_function = on_final_text

    # GUI Setup
    root = tk.Tk()
    root.title("Speech to Text (Faster Whisper)")
    root.geometry("650x500")

    tk.Label(root, text="Select Microphone:", font=("Arial", 10)).pack(pady=5)

    mic_list = get_microphones()
    mic_dropdown = ttk.Combobox(root, values=mic_list, state="readonly", width=50)
    mic_dropdown.pack()
    if mic_list:
        mic_dropdown.current(0)

    # Listening indicator label
    listening_label = tk.Label(root, text="", font=("Arial", 12, "bold"))
    listening_label.pack(pady=5)

    # Button frame
    button_frame = tk.Frame(root)
    button_frame.pack(pady=10)

    record_button = tk.Button(
        button_frame,
        text="Start Recording",
        command=start_recording,
        bg="green",
        fg="white",
        width=20,
        height=2,
    )
    record_button.grid(row=0, column=0, padx=5)

    stop_button = tk.Button(
        button_frame,
        text="Stop Recording",
        command=stop_recording,
        bg="red",
        fg="white",
        width=20,
        height=2,
    )
    stop_button.grid(row=0, column=1, padx=5)

    tk.Label(root, text="Transcription:", font=("Arial", 10)).pack(pady=5)

    output_box = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=70, height=15)
    output_box.pack(pady=10, padx=10)

    # Start the main event loop
    root.mainloop()
