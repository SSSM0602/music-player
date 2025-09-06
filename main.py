import sys
import requests
import yt_dlp
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog, QLineEdit
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput


class MusicPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Qt Music Player")
        self.setFixedSize(500, 500)

        # Central widget + layout
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Album art placeholder
        self.album_label = QLabel()
        self.album_label.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap(200, 200)
        pixmap.fill(Qt.darkGray)
        self.album_label.setPixmap(pixmap)
        layout.addWidget(self.album_label)

        # Song title
        self.song_label = QLabel("No song loaded")
        self.song_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.song_label)

        # YouTube input
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste YouTube URL here...")
        layout.addWidget(self.url_input)

        # Controls
        controls = QHBoxLayout()
        self.prev_btn = QPushButton("⏮")
        self.play_btn = QPushButton("▶️")
        self.next_btn = QPushButton("⏭")
        self.open_btn = QPushButton("📂")
        self.yt_btn = QPushButton("▶️ YouTube")

        for btn in (self.prev_btn, self.play_btn, self.next_btn, self.open_btn, self.yt_btn):
            btn.setFixedSize(80, 40)
            controls.addWidget(btn)

        layout.addLayout(controls)

        # Media player setup
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        # Button connections
        self.play_btn.clicked.connect(self.toggle_play)
        self.prev_btn.clicked.connect(self.prev_track)
        self.next_btn.clicked.connect(self.next_track)
        self.open_btn.clicked.connect(self.open_file)
        self.yt_btn.clicked.connect(self.play_youtube)

        self.is_playing = False
        self.playlist = []  # list of file paths or stream URLs
        self.current_index = -1

    def open_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "Open Audio File", "", "Audio Files (*.mp3 *.wav *.m4a)")
        if file:
            self.playlist = [file]
            self.current_index = 0
            self.load_track(file)

    def play_youtube(self):
        url = self.url_input.text().strip()
        if not url:
            return

        # Extract best audio + metadata with yt-dlp
        ydl_opts = {"format": "bestaudio/best", "quiet": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info["url"]  # direct stream URL
            title = info.get("title", "YouTube Audio")
            thumbnail_url = info.get("thumbnail")

        self.playlist = [audio_url]
        self.current_index = 0
        self.load_track(audio_url, title, thumbnail_url)

    def load_track(self, file_or_url, title=None, thumbnail_url=None):
        url = QUrl(file_or_url) if "http" in file_or_url else QUrl.fromLocalFile(file_or_url)
        self.player.setSource(url)
        self.song_label.setText(title if title else file_or_url.split("/")[-1])
        self.play_btn.setText("▶️")
        self.is_playing = False

        # Load album art if available
        if thumbnail_url:
            try:
                img_data = requests.get(thumbnail_url).content
                pixmap = QPixmap()
                pixmap.loadFromData(img_data)
                scaled = pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.album_label.setPixmap(scaled)
            except Exception as e:
                print("Failed to load thumbnail:", e)

    def toggle_play(self):
        if self.current_index == -1:
            return

        if self.is_playing:
            self.player.pause()
            self.play_btn.setText("▶️")
            self.is_playing = False
        else:
            self.player.play()
            self.play_btn.setText("⏸")
            self.is_playing = True

    def prev_track(self):
        if self.playlist and self.current_index > 0:
            self.current_index -= 1
            self.load_track(self.playlist[self.current_index])

    def next_track(self):
        if self.playlist and self.current_index < len(self.playlist) - 1:
            self.current_index += 1
            self.load_track(self.playlist[self.current_index])


if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = MusicPlayer()
    player.show()
    sys.exit(app.exec())
