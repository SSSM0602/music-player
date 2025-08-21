
# main.py
# Qt music player starter that can STREAM from YouTube (audio-only) and DOWNLOAD using yt-dlp.
# Requirements: Python 3.10+, PySide6, yt-dlp, ffmpeg (for post-processing to mp3/m4a)

import sys
import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QUrl, Signal, QObject
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLineEdit,
    QPushButton,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
    QProgressBar,
    QMessageBox,
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

try:
    from yt_dlp import YoutubeDL
except Exception as e:
    YoutubeDL = None


class YTDLPWorker(QObject):
    progress = Signal(float)  # 0-100
    message = Signal(str)
    finished = Signal(bool, str)  # success, path_or_error

    def __init__(self, download_dir: Path):
        super().__init__()
        self.download_dir = download_dir

    def _ydl(self, opts: dict) -> YoutubeDL:
        return YoutubeDL(opts)

    def best_audio_stream_url(self, url: str) -> Optional[str]:
        opts = {"quiet": True, "nocheckcertificate": True}
        with self._ydl(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            # Pick best audio-only format with highest abr
            audio_formats = [f for f in info.get("formats", []) if f.get("acodec") != "none" and f.get("vcodec") == "none"]
            if not audio_formats:
                # Fallback: allow muxed if no audio-only
                audio_formats = [f for f in info.get("formats", []) if f.get("acodec") != "none"]
            if not audio_formats:
                return None
            best = max(audio_formats, key=lambda f: (f.get("abr") or 0, f.get("tbr") or 0))
            return best.get("url")

    def download(self, url: str, audio_format: str = "mp3"):
        # Ensure directory exists
        self.download_dir.mkdir(parents=True, exist_ok=True)

        def hook(d):
            if d.get('status') == 'downloading':
                p = d.get('downloaded_bytes') or 0
                t = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                if t:
                    self.progress.emit(float(p) * 100.0 / float(t))
            elif d.get('status') == 'finished':
                self.progress.emit(100.0)

        outtmpl = str(self.download_dir / '%(title)s.%(ext)s')
        # Convert to chosen audio format using ffmpeg (must be installed)
        post = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': audio_format,
            'preferredquality': '0'
        }]

        opts = {
            'format': 'bestaudio/best',
            'outtmpl': outtmpl,
            'noprogress': True,
            'quiet': True,
            'nocheckcertificate': True,
            'postprocessors': post,
            'progress_hooks': [hook],
        }

        try:
            with self._ydl(opts) as ydl:
                result = ydl.download([url])
            # yt-dlp returns 0 on success
            if result == 0:
                self.finished.emit(True, str(self.download_dir))
            else:
                self.finished.emit(False, 'Download failed')
        except Exception as e:
            self.finished.emit(False, str(e))


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Qt Music Player (YouTube)")
        self.resize(720, 420)

        # UI Elements
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste YouTube URL (video, music, playlist item)...")

        self.stream_btn = QPushButton("Stream")
        self.download_btn = QPushButton("Download")
        self.pick_dir_btn = QPushButton("Set Download Folder")

        self.status_label = QLabel("Ready")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        # Media Player
        self.audio_output = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)

        # Basic transport controls
        self.play_btn = QPushButton("Play")
        self.pause_btn = QPushButton("Pause")
        self.stop_btn = QPushButton("Stop")

        # Layout
        top = QHBoxLayout()
        top.addWidget(QLabel("URL:"))
        top.addWidget(self.url_input)

        buttons = QHBoxLayout()
        buttons.addWidget(self.stream_btn)
        buttons.addWidget(self.download_btn)
        buttons.addWidget(self.pick_dir_btn)

        transport = QHBoxLayout()
        transport.addWidget(self.play_btn)
        transport.addWidget(self.pause_btn)
        transport.addWidget(self.stop_btn)

        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addLayout(buttons)
        root.addWidget(self.status_label)
        root.addWidget(self.progress)
        root.addLayout(transport)

        # State
        self.download_dir = Path.cwd() / "downloads"
        self.worker = YTDLPWorker(self.download_dir)

        # Signals
        self.stream_btn.clicked.connect(self.on_stream)
        self.download_btn.clicked.connect(self.on_download)
        self.pick_dir_btn.clicked.connect(self.on_pick_dir)
        self.play_btn.clicked.connect(self.player.play)
        self.pause_btn.clicked.connect(self.player.pause)
        self.stop_btn.clicked.connect(self.player.stop)

        self.player.playbackStateChanged.connect(self.on_state)
        self.player.errorOccurred.connect(self.on_error)

        # Worker signals
        self.worker.progress.connect(lambda p: self.progress.setValue(int(p)))
        self.worker.message.connect(self.set_status)
        self.worker.finished.connect(self.on_download_finished)

        if YoutubeDL is None:
            QMessageBox.critical(self, "Missing dependency", "yt-dlp is not installed. Run: pip install yt-dlp")

    def set_status(self, text: str):
        self.status_label.setText(text)

    def on_state(self, state):
        # Update UI status lightly
        st = {QMediaPlayer.PlayingState: "Playing", QMediaPlayer.PausedState: "Paused", QMediaPlayer.StoppedState: "Stopped"}.get(state, "")
        if st:
            self.set_status(st)

    def on_error(self, error, error_string):
        if error:
            QMessageBox.warning(self, "Playback error", error_string)

    def on_pick_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Choose download folder", str(self.download_dir))
        if path:
            self.download_dir = Path(path)
            self.worker.download_dir = self.download_dir
            self.set_status(f"Download dir: {self.download_dir}")

    def on_stream(self):
        url = self.url_input.text().strip()
        if not url:
            return
        self.setEnabled(False)
        self.set_status("Resolving audio stream...")

        # Use a lightweight thread via QtConcurrent to avoid freezing UI
        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=1)

        def task():
            try:
                s_url = self.worker.best_audio_stream_url(url)
                return True, s_url
            except Exception as e:
                return False, str(e)

        future = executor.submit(task)

        def done(_):
            self.setEnabled(True)
            ok, data = future.result()
            if not ok or not data:
                QMessageBox.warning(self, "Stream error", data or "No playable audio format found")
                self.set_status("Ready")
                return
            # Play via QMediaPlayer directly from remote URL
            self.player.setSource(QUrl(data))
            self.player.play()
            self.set_status("Streaming from YouTube")

        # Use a single-shot timer to poll completion (keeps it simple without signals)
        from PySide6.QtCore import QTimer
        def poll():
            if future.done():
                done(None)
            else:
                QTimer.singleShot(100, poll)
        QTimer.singleShot(0, poll)

    def on_download(self):
        url = self.url_input.text().strip()
        if not url:
            return
        if YoutubeDL is None:
            QMessageBox.critical(self, "Missing dependency", "yt-dlp is not installed. Run: pip install yt-dlp")
            return

        self.progress.setValue(0)
        self.set_status("Downloading...")
        self.setEnabled(False)

        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=1)

        def task():
            self.worker.download(url, audio_format="mp3")

        future = executor.submit(task)

        from PySide6.QtCore import QTimer
        def poll():
            if future.done():
                self.setEnabled(True)
                # worker.finished will update final status
            else:
                QTimer.singleShot(150, poll)
        QTimer.singleShot(0, poll)

    def on_download_finished(self, success: bool, path_or_error: str):
        self.setEnabled(True)
        if success:
            self.set_status(f"Saved to: {self.download_dir}")
            QMessageBox.information(self, "Done", f"Audio saved in: {self.download_dir}")
        else:
            self.set_status("Ready")
            QMessageBox.warning(self, "Download error", path_or_error)


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()

# -----------------------------
# requirements.txt (example)
# PySide6>=6.6
# yt-dlp>=2024.7.7
# (Install ffmpeg separately: https://ffmpeg.org/)
