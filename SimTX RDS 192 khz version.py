import socket
import threading
import tkinter as tk
from tkinter import ttk
import numpy as np
import sounddevice as sd


class MPXStreamerGUI:

  def __init__(self, root):
    self.root = root
    self.root.title("Set SimTX source to Gnu Radio IQ, set port to 1000.")
    self.root.geometry("450x320")
    self.root.resizable(False, False)

    self.is_running = False
    self.stream_thread = None
    self.device_names = []
    self.device_map = {}

    tk.Label(
        root,
        text="MPX",
        font=("Arial", 11, "bold"),
    ).pack(pady=10)


    dev_frame = tk.LabelFrame(
        root, text=" Set to stereo tool output, set simtx bandwidth to 192000. ", padx=10, pady=10
    )
    dev_frame.pack(fill="x", padx=15, pady=5)

    self.device_combobox = ttk.Combobox(dev_frame, state="readonly", width=45)
    self.device_combobox.pack(fill="x", pady=5)

    tk.Button(
        dev_frame, text="Refresh Devices", command=self.refresh_audio_devices
    ).pack(anchor="e")


    ctrl_frame = tk.Frame(root, pady=15)
    ctrl_frame.pack(fill="x", padx=15)

    self.status_label = tk.Label(
        ctrl_frame, text="Status: Stopped", fg="red", font=("Arial", 10, "bold")
    )
    self.status_label.pack(pady=5)

    btn_row = tk.Frame(ctrl_frame)
    btn_row.pack()

    self.start_btn = tk.Button(
        btn_row,
        text="Start Stream",
        bg="green",
        fg="white",
        width=14,
        command=self.start_streaming,
    )
    self.start_btn.pack(side="left", padx=10)

    self.stop_btn = tk.Button(
        btn_row,
        text="Stop Stream",
        bg="red",
        fg="white",
        width=14,
        command=self.stop_streaming,
        state="disabled",
    )
    self.stop_btn.pack(side="left", padx=10)

    self.root.after(100, self.refresh_audio_devices)

  def refresh_audio_devices(self):
    self.device_names.clear()
    self.device_map.clear()
    try:
      devices = sd.query_devices()
      for idx, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
          name = f"{dev['name']} (ID: {idx})"
          self.device_names.append(name)
          self.device_map[name] = idx

      self.device_combobox["values"] = self.device_names
      if self.device_names:
        match_idx = 0
        for i, name in enumerate(self.device_names):
          if "Line 1" in name:
            match_idx = i
            break
        self.device_combobox.current(match_idx)
    except Exception as e:
      print(f"Device error: {e}")

  def start_streaming(self):
    selected_name = self.device_combobox.get()
    if not selected_name:
      return

    device_idx = self.device_map.get(selected_name)

    self.is_running = True
    self.start_btn.config(state="disabled")
    self.stop_btn.config(state="normal")
    self.device_combobox.config(state="disabled")
    self.status_label.config(text="Status: Streaming to SimTX...", fg="green")

    self.stream_thread = threading.Thread(
        target=self.stream_worker, args=(device_idx,), daemon=True
    )
    self.stream_thread.start()

  def stop_streaming(self):
    self.is_running = False
    try:
      self.start_btn.config(state="normal")
      self.stop_btn.config(state="disabled")
      self.device_combobox.config(state="readonly")
      self.status_label.config(text="Status: Stopped", fg="red")
    except Exception:
      pass

  def stream_worker(self, device_idx):
    TCP_IP = "127.0.0.1"
    TCP_PORT = 1000
    SAMPLE_RATE = 192000
    MAX_DEVIATION = 75000.0

    fm_sensitivity = 2.0 * np.pi * MAX_DEVIATION / SAMPLE_RATE
    sock = None

    try:
      with sd.InputStream(
          device=device_idx,
          channels=1,
          samplerate=SAMPLE_RATE,
          dtype="float32",
      ) as stream:
        while self.is_running:
          mpx_chunk, overflow = stream.read(4800)
          mpx_data = mpx_chunk.flatten()

          if len(mpx_data) == 0:
            continue


          phase = np.cumsum(mpx_data * fm_sensitivity)
          iq_data = np.exp(1j * phase).astype(np.complex64)

          if sock is None:
            try:
              s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
              s.connect((TCP_IP, TCP_PORT))
              s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
              sock = s
            except OSError:
              sock = None

          if sock is not None:
            try:
              sock.sendall(iq_data.tobytes())
            except OSError:
              sock.close()
              sock = None
    except Exception as e:
      print(f"Worker Exception: {e}")
    finally:
      if sock:
        sock.close()
      try:
        self.root.after(0, self.stop_streaming)
      except Exception:
        pass


if __name__ == "__main__":
  root = tk.Tk()
  app = MPXStreamerGUI(root)
  root.mainloop()
