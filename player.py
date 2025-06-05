import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QSlider, QLabel, QListWidget, QFileDialog, QDesktopWidget)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QStyle
from mutagen.mp3 import MP3
import pygame
import uuid

class MP3Player(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MP3 Player - AlSong Style")
        self.setFixedSize(600, 200)  # Rectangular player window
        self.center_window()

        # Initialize pygame mixer
        pygame.mixer.init()

        # Widgets
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Song info
        self.song_label = QLabel("No song selected")
        self.layout.addWidget(self.song_label)

        # Playback controls
        self.control_layout = QHBoxLayout()
        self.play_button = QPushButton()
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.stop_button = QPushButton()
        self.stop_button.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.prev_button = QPushButton()
        self.prev_button.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipBackward))
        self.next_button = QPushButton()
        self.next_button.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipForward))
        self.playlist_button = QPushButton()
        self.playlist_button.setIcon(self.style().standardIcon(QStyle.SP_FileDialogListView))
        self.control_layout.addWidget(self.prev_button)
        self.control_layout.addWidget(self.play_button)
        self.control_layout.addWidget(self.stop_button)
        self.control_layout.addWidget(self.next_button)
        self.control_layout.addWidget(self.playlist_button)
        self.layout.addLayout(self.control_layout)

        # Seek slider
        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setMinimum(0)
        self.seek_slider.setValue(0)
        self.layout.addWidget(self.seek_slider)

        # Volume slider
        self.volume_label = QLabel("Volume")
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(50)
        self.layout.addWidget(self.volume_label)
        self.layout.addWidget(self.volume_slider)

        # Playlist widget (initially hidden)
        self.playlist_widget = QWidget()
        self.playlist_layout = QVBoxLayout(self.playlist_widget)
        self.playlist = QListWidget()
        self.playlist.setDragDropMode(QListWidget.InternalMove)
        self.playlist.setAcceptDrops(True)
        self.playlist_layout.addWidget(self.playlist)
        self.add_song_button = QPushButton("Add Song")
        self.add_song_button.setIcon(self.style().standardIcon(QStyle.SP_FileDialogNewFolder))
        self.playlist_layout.addWidget(self.add_song_button)
        self.playlist_widget.hide()  # Hide by default
        self.layout.addWidget(self.playlist_widget)

        # Player state
        self.current_song = None
        self.is_playing = False
        self.playlist_songs = []
        self.is_playlist_visible = False

        # Connect signals
        self.play_button.clicked.connect(self.play_pause)
        self.stop_button.clicked.connect(self.stop)
        self.prev_button.clicked.connect(self.prev_song)
        self.next_button.clicked.connect(self.next_song)
        self.playlist_button.clicked.connect(self.toggle_playlist)
        self.add_song_button.clicked.connect(self.add_song)
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.seek_slider.sliderMoved.connect(self.seek)
        self.playlist.itemDoubleClicked.connect(self.play_selected_song)
        self.playlist.model().rowsMoved.connect(self.update_playlist_order)

        # Timer for updating seek slider
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_seek_slider)
        self.timer.start(1000)  # Update every second

        # Style
        self.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; padding: 5px; border-radius: 5px; }
            QListWidget { background-color: #f0f0f0; }
            QSlider::groove:horizontal { background: #d3d3d3; height: 8px; }
            QSlider::handle:horizontal { background: #4CAF50; width: 16px; }
        """)

    def center_window(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def toggle_playlist(self):
        if self.is_playlist_visible:
            self.playlist_widget.hide()
            self.is_playlist_visible = False
            self.setFixedSize(600, 200)  # Shrink window
            self.playlist_button.setIcon(self.style().standardIcon(QStyle.SP_FileDialogListView))
        else:
            self.playlist_widget.show()
            self.is_playlist_visible = True
            self.setFixedSize(600, 500)  # Expand window to include playlist (200 + 300)
            self.playlist_button.setIcon(self.style().standardIcon(QStyle.SP_FileDialogListView))
        self.center_window()

    def add_song(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open MP3 File", "", "MP3 Files (*.mp3)")
        if file_name:
            self.playlist_songs.append(file_name)
            song = MP3(file_name)
            title = song.get("TIT2", os.path.basename(file_name))
            self.playlist.addItem(str(title))

    def play_pause(self):
        if not self.current_song and self.playlist_songs:
            self.current_song = self.playlist_songs[0]
            pygame.mixer.music.load(self.current_song)
            pygame.mixer.music.play()
            self.is_playing = True
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
            self.update_song_info()
        elif self.is_playing:
            pygame.mixer.music.pause()
            self.is_playing = False
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        else:
            pygame.mixer.music.unpause()
            self.is_playing = True
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))

    def stop(self):
        pygame.mixer.music.stop()
        self.is_playing = False
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.seek_slider.setValue(0)

    def prev_song(self):
        if self.current_song and self.playlist_songs:
            index = self.playlist_songs.index(self.current_song)
            if index > 0:
                self.current_song = self.playlist_songs[index - 1]
                pygame.mixer.music.load(self.current_song)
                pygame.mixer.music.play()
                self.is_playing = True
                self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
                self.update_song_info()

    def next_song(self):
        if self.current_song and self.playlist_songs:
            index = self.playlist_songs.index(self.current_song)
            if index < len(self.playlist_songs) - 1:
                self.current_song = self.playlist_songs[index + 1]
                pygame.mixer.music.load(self.current_song)
                pygame.mixer.music.play()
                self.is_playing = True
                self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
                self.update_song_info()

    def play_selected_song(self, item):
        index = self.playlist.row(item)
        self.current_song = self.playlist_songs[index]
        pygame.mixer.music.load(self.current_song)
        pygame.mixer.music.play()
        self.is_playing = True
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        self.update_song_info()

    def update_song_info(self):
        if self.current_song:
            song = MP3(self.current_song)
            title = song.get("TIT2", os.path.basename(self.current_song))
            artist = song.get("TPE1", "Unknown Artist")
            self.song_label.setText(f"Now Playing: {title} - {artist}")
            self.seek_slider.setMaximum(int(song.info.length))

    def set_volume(self):
        volume = self.volume_slider.value() / 100
        pygame.mixer.music.set_volume(volume)

    def seek(self):
        position = self.seek_slider.value()
        pygame.mixer.music.set_pos(position)

    def update_seek_slider(self):
        if self.is_playing and self.current_song:
            position = pygame.mixer.music.get_pos() / 1000  # Convert to seconds
            self.seek_slider.setValue(int(position))

    def update_playlist_order(self):
        # Sync playlist_songs with reordered playlist
        new_order = []
        for i in range(self.playlist.count()):
            item = self.playlist.item(i)
            for song_path in self.playlist_songs:
                song = MP3(song_path)
                title = song.get("TIT2", os.path.basename(song_path))
                if str(title) == item.text():
                    new_order.append(song_path)
                    break
        self.playlist_songs = new_order

if __name__ == '__main__':
    app = QApplication(sys.argv)
    player = MP3Player()
    player.show()
    sys.exit(app.exec_())