import tkinter as tk
from tkinter import ttk, scrolledtext
import sounddevice as sd
import threading
import queue
from vosk import Model, KaldiRecognizer
import json

# Load Vosk model (make sure you have the model folder available)
# MODEL_PATH =   # Change if needed
model = Model(lang="en-us")

# Global variables
audio_queue = queue.Queue()
recording = False
recognizer = None


# Get available microphones
def get_microphones():
    devices = sd.query_devices()
    return [dev["name"] for dev in devices if dev["max_input_channels"] > 0]


# Audio callback to collect audio chunks
def audio_callback(indata, frames, time, status):
    if status:
        print(status)
    audio_queue.put(bytes(indata))


# Recording logic in a thread
def record_audio(device_index, output_widget):
    global recording, recognizer
    recognizer = KaldiRecognizer(model, 16000)

    with sd.RawInputStream(
        samplerate=16000,
        blocksize=8000,
        device=device_index,
        dtype="int16",
        channels=1,
        callback=audio_callback,
    ):
        while recording:
            data = audio_queue.get()
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())["text"]
            else:
                result = json.loads(recognizer.PartialResult())["partial"]
            output_widget.insert(tk.END, result + "\n")
            output_widget.see(tk.END)


# Start recording button handler
def start_recording():
    global recording
    if recording:
        return
    recording = True
    device_index = mic_dropdown.current()
    threading.Thread(
        target=record_audio, args=(device_index, output_box), daemon=True
    ).start()


# Stop recording button handler
def stop_recording():
    global recording
    recording = False


# GUI Setup
root = tk.Tk()
root.title("Speech to Text (Vosk)")

tk.Label(root, text="Select Microphone:").pack()

mic_list = get_microphones()
mic_dropdown = ttk.Combobox(root, values=mic_list, state="readonly")
mic_dropdown.pack()
mic_dropdown.current(0)

record_button = tk.Button(
    root,
    text="Start Recording",
    command=start_recording,
    bg="green",
    fg="white",
    width=20,
    height=2,
)
record_button.pack(pady=5)

stop_button = tk.Button(
    root,
    text="Stop Recording",
    command=stop_recording,
    bg="red",
    fg="white",
    width=20,
    height=2,
)
stop_button.pack(pady=5)

output_box = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=60, height=15)
output_box.pack(pady=10)

root.mainloop()
