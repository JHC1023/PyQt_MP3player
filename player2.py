import sys
import os
import shutil
import re
import urllib.request
import random
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QSlider, QLabel, QListWidget, QFileDialog, QDesktopWidget,
                             QMenuBar, QAction, QLineEdit, QMessageBox, QListWidgetItem)
from PyQt5.QtCore import Qt, QTimer, QEvent
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QStyle
from mutagen.mp3 import MP3
import pygame
import uuid
from googleapiclient.discovery import build
import yt_dlp
import threading

class CustomListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.player = parent

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete and self.player:
            self.player.delete_song()
        else:
            super().keyPressEvent(event)

class MP3Player(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MP3 Player - AlSong Style")
        self.setFixedSize(500, 250)
        self.center_window()

        pygame.mixer.init()

        self.current_song = None
        self.is_playing = False
        self.playlist_songs = []
        self.is_playlist_visible = False
        self.repeat_mode = "off"
        self.previous_repeat_mode = "off"  # Shuffle 해제 시 복원할 반복 모드 저장
        self.is_shuffle = False
        self.is_seeking = False
        self.current_position = 0
        self.last_volume = 50
        self.all_songs = []

        # YouTube API 설정
        self.YOUTUBE_API_KEY = ""  # 실제 API 키로 교체
        try:
            self.youtube = build('youtube', 'v3', developerKey=self.YOUTUBE_API_KEY)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to initialize YouTube API: {str(e)}")
            self.youtube = None

        # ffmpeg 경로 설정
        self.ffmpeg_path = self._get_ffmpeg_path()
        if not self.ffmpeg_path:
            QMessageBox.critical(self, "Error", "ffmpeg is not installed or path is incorrect. Please check ffmpeg installation.")

        self.download_dir = os.path.join(os.path.expanduser("~"), "Downloads", "MP3Player")
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

        self.menu_bar = self.menuBar()
        self.setup_menus()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.top_layout = QHBoxLayout()
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(150, 150)
        self.thumbnail_label.setStyleSheet("background-color: #F5F6F5; border: 1px solid #1E90FF;")
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.top_layout.addWidget(self.thumbnail_label)

        self.info_layout = QVBoxLayout()
        self.title_label = QLabel("No song selected")
        self.artist_label = QLabel("")
        self.info_layout.addWidget(self.title_label)
        self.info_layout.addWidget(self.artist_label)
        self.top_layout.addLayout(self.info_layout)
        self.top_layout.addStretch()
        self.main_layout.addLayout(self.top_layout)

        self.seek_layout = QHBoxLayout()
        self.current_time_label = QLabel("0:00")
        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setMinimum(0)
        self.seek_slider.setValue(0)
        self.seek_slider.setFixedWidth(400)  # 재생바 길이 늘림
        self.total_time_label = QLabel("0:00")
        self.seek_layout.addStretch()
        self.seek_layout.addWidget(self.current_time_label)
        self.seek_layout.addWidget(self.seek_slider)
        self.seek_layout.addWidget(self.total_time_label)
        self.seek_layout.addStretch()
        self.main_layout.addLayout(self.seek_layout)

        self.control_layout = QHBoxLayout()
        self.prev_button = QPushButton()
        self.prev_button.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipBackward))
        self.play_button = QPushButton()
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.stop_button = QPushButton()
        self.stop_button.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.next_button = QPushButton()
        self.next_button.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipForward))
        self.playlist_button = QPushButton()
        self.playlist_button.setIcon(self.style().standardIcon(QStyle.SP_FileDialogListView))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(50)
        self.volume_slider.setFixedWidth(100)
        self.volume_button = QPushButton()
        self.volume_button.setIcon(self.style().standardIcon(QStyle.SP_MediaVolume))
        self.repeat_button = QPushButton()
        self.repeat_button.setFixedWidth(60)
        self.repeat_button.clicked.connect(self.cycle_repeat_mode)
        # 초기 상태 설정: 반복 끄기
        self.repeat_button.setIcon(QIcon("images/repeat_off.png"))
        self.control_layout.addStretch()
        self.control_layout.addWidget(self.prev_button)
        self.control_layout.addWidget(self.play_button)
        self.control_layout.addWidget(self.stop_button)
        self.control_layout.addWidget(self.next_button)
        self.control_layout.addWidget(self.playlist_button)
        self.control_layout.addWidget(self.volume_slider)
        self.control_layout.addWidget(self.volume_button)
        self.control_layout.addWidget(self.repeat_button)
        self.control_layout.addStretch()
        self.main_layout.addLayout(self.control_layout)

        self.playlist_widget = QWidget()
        self.playlist_layout = QVBoxLayout(self.playlist_widget)
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search songs...")
        self.search_bar.textChanged.connect(self.filter_songs)
        self.playlist_layout.addWidget(self.search_bar)
        self.youtube_search_bar = QLineEdit()
        self.youtube_search_bar.setPlaceholderText("Search YouTube...")
        self.youtube_search_bar.returnPressed.connect(self.search_youtube)
        self.playlist_layout.addWidget(self.youtube_search_bar)
        self.youtube_results = QListWidget()
        self.youtube_results.itemDoubleClicked.connect(self.download_youtube)
        self.youtube_results.hide()
        self.playlist_layout.addWidget(self.youtube_results)
        self.playlist = CustomListWidget(self)
        self.playlist.setDragDropMode(QListWidget.InternalMove)
        self.playlist.setAcceptDrops(True)
        self.playlist_layout.addWidget(self.playlist)
        self.button_layout = QHBoxLayout()
        self.add_song_button = QPushButton("Add")
        self.add_song_button.setIcon(self.style().standardIcon(QStyle.SP_FileDialogNewFolder))
        self.delete_song_button = QPushButton("Delete")
        self.delete_song_button.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        self.button_layout.addWidget(self.add_song_button)
        self.button_layout.addWidget(self.delete_song_button)
        self.playlist_layout.addLayout(self.button_layout)
        self.playlist_widget.hide()
        self.main_layout.addWidget(self.playlist_widget)

        self.play_button.clicked.connect(self.play_pause)
        self.stop_button.clicked.connect(self.stop)
        self.prev_button.clicked.connect(self.prev_song)
        self.next_button.clicked.connect(self.next_song)
        self.playlist_button.clicked.connect(self.toggle_playlist)
        self.volume_button.clicked.connect(self.toggle_mute)
        self.add_song_button.clicked.connect(self.add_song)
        self.delete_song_button.clicked.connect(self.delete_song)
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.seek_slider.sliderPressed.connect(self.start_seeking)
        self.seek_slider.sliderReleased.connect(self.stop_seeking)
        self.seek_slider.valueChanged.connect(self.seek)
        self.playlist.itemDoubleClicked.connect(self.play_selected_song)
        self.playlist.model().rowsMoved.connect(self.update_playlist_order)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_seek_slider)
        self.timer.start(1000)

        self.setStyleSheet("""
            QMainWindow { background-color: #F5F6F5; }
            QPushButton { 
                background-color: #1E90FF; 
                color: white; 
                padding: 5px; 
                border-radius: 5px; 
                border: 1px solid #1565C0;
            }
            QPushButton:hover { background-color: #42A5F5; }
            QListWidget { background-color: #FFFFFF; border: 1px solid #1E90FF; }
            QLineEdit { 
                background-color: #FFFFFF; 
                border: 1px solid #1E90FF; 
                padding: 5px;
                border-radius: 3px;
            }
            QSlider::groove:horizontal#seek_slider { 
                background: #BBDEFB; 
                height: 8px; 
                border-radius: 4px;
            }
            QSlider::handle:horizontal#seek_slider { 
                background: #1E90FF; 
                width: 16px; 
                border-radius: 8px;
                border: 1px solid #1565C0;
            }
            QSlider::groove:horizontal#volume_slider { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #BBDEFB, stop:1 #1E90FF);
                height: 8px; 
                border-radius: 4px;
                clip-path: polygon(0% 100%, 100% 100%, 100% 0%, 0% 0%);
            }
            QSlider::handle:horizontal#volume_slider { 
                background: #FFFFFF; 
                width: 12px; 
                height: 12px; 
                border-radius: 6px;
                border: 1px solid #1565C0;
                margin: -2px 0;
            }
            QLabel { color: #1565C0; }
        """)
        self.seek_slider.setObjectName("seek_slider")
        self.volume_slider.setObjectName("volume_slider")

    def _get_ffmpeg_path(self):
        """ffmpeg 실행 파일 경로 탐지"""
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            return os.path.dirname(ffmpeg_path)
        custom_path = r"A:\Users\KimJoungMin\Documents\ffmpeg-2024-09-22-git-a577d313b2-full_build\bin"
        if os.path.exists(os.path.join(custom_path, "ffmpeg.exe")):
            return custom_path
        return None

    def _parse_title(self, title):
        """유튜브 제목에서 아티스트와 곡명 분리"""
        patterns = [
            r'^(.*?)\s*-\s*(.*?)$',  # "아티스트 - 곡명"
            r'^(.*?)\s*by\s*(.*?)$',  # "곡명 by 아티스트"
            r'^(.*?)\s*\((.*?)\)$',  # "곡명 (아티스트)"
            r'^(.*?)\s*[\|]\s*(.*?)$',  # "아티스트 | 곡명"
        ]
        for pattern in patterns:
            match = re.match(pattern, title.strip(), re.IGNORECASE)
            if match:
                parts = match.groups()
                if len(parts) == 2:
                    artist, song = parts
                    artist = artist.strip()
                    song = song.strip()
                    if pattern == r'^(.*?)\s*by\s*(.*?)$' or pattern == r'^(.*?)\s*\((.*?)\)$':
                        artist, song = song, artist
                    if artist and song:
                        return song, artist
        return title.strip(), "Unknown Artist"

    def setup_menus(self):
        file_menu = self.menu_bar.addMenu("파일")
        open_action = QAction("열기", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_song)
        file_menu.addAction(open_action)
        add_action = QAction("추가", self)
        add_action.setShortcut("Ctrl+A")
        add_action.triggered.connect(self.add_song)
        file_menu.addAction(add_action)

        playback_menu = self.menu_bar.addMenu("재생")
        prev_action = QAction("이전 곡", self)
        prev_action.setShortcut("Z")
        prev_action.triggered.connect(self.prev_song)
        playback_menu.addAction(prev_action)
        play_pause_action = QAction("재생/일시정지", self)
        play_pause_action.setShortcuts(["X", "Space"])
        play_pause_action.triggered.connect(self.play_pause)
        playback_menu.addAction(play_pause_action)
        stop_action = QAction("정지", self)
        stop_action.setShortcut("V")
        stop_action.triggered.connect(self.stop)
        playback_menu.addAction(stop_action)
        next_action = QAction("다음 곡", self)
        next_action.setShortcut("B")
        next_action.triggered.connect(self.next_song)
        playback_menu.addAction(next_action)
        playback_menu.addSeparator()
        backward_action = QAction("뒤로", self)
        backward_action.setShortcut("Left")
        backward_action.triggered.connect(lambda: self.seek_relative(-5))
        playback_menu.addAction(backward_action)
        forward_action = QAction("앞으로", self)
        forward_action.setShortcut("Right")
        forward_action.triggered.connect(lambda: self.seek_relative(5))
        playback_menu.addAction(forward_action)
        playback_menu.addSeparator()
        self.repeat_action = QAction("반복 끄기", self)
        self.repeat_action.setShortcut("T")
        self.repeat_action.triggered.connect(self.cycle_repeat_mode)
        playback_menu.addAction(self.repeat_action)
        shuffle_action = QAction("무작위 재생", self)
        shuffle_action.setShortcut("A")
        shuffle_action.triggered.connect(self.toggle_shuffle)
        playback_menu.addAction(shuffle_action)
        volume_up_action = QAction("소리 높임", self)
        volume_up_action.setShortcut("Up")
        volume_up_action.triggered.connect(lambda: self.adjust_volume(10))
        playback_menu.addAction(volume_up_action)
        volume_down_action = QAction("소리 낮춤", self)
        volume_down_action.setShortcut("Down")
        volume_down_action.triggered.connect(lambda: self.adjust_volume(-10))
        playback_menu.addAction(volume_down_action)
        mute_action = QAction("음소거", self)
        mute_action.setShortcut("M")
        mute_action.triggered.connect(self.toggle_mute)
        playback_menu.addAction(mute_action)

        help_menu = self.menu_bar.addMenu("도움말")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def center_window(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def toggle_playlist(self):
        if self.is_playlist_visible:
            self.playlist_widget.hide()
            self.youtube_results.hide()
            self.is_playlist_visible = False
            self.setFixedSize(500, 250)
        else:
            self.playlist_widget.show()
            self.is_playlist_visible = True
            self.setFixedSize(500, 700)

    def search_youtube(self):
        if not self.youtube:
            QMessageBox.critical(self, "Error", "YouTube API is not initialized.")
            return
        if not self.ffmpeg_path:
            QMessageBox.critical(self, "Error", "ffmpeg is not installed. Please install it first.")
            return
        query = self.youtube_search_bar.text().strip()
        if not query:
            QMessageBox.warning(self, "Warning", "Please enter a search query.")
            return
        self.youtube_results.clear()
        self.youtube_results.show()
        try:
            request = self.youtube.search().list(
                q=query,
                part="snippet",
                maxResults=10,
                type="video"
            )
            response = request.execute()
            for item in response.get("items", []):
                title = item["snippet"]["title"]
                video_id = item["id"]["videoId"]
                thumbnail_url = item["snippet"]["thumbnails"]["default"]["url"]
                list_item = QListWidgetItem(f"{title} [youtube.com/watch?v={video_id}]")
                list_item.setData(Qt.UserRole, thumbnail_url)
                self.youtube_results.addItem(list_item)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to search YouTube: {str(e)}")

    def download_youtube(self, item):
        if not self.ffmpeg_path:
            QMessageBox.critical(self, "Error", "ffmpeg is not installed. Please install it first.")
            return
        video_url = item.text().split("[")[-1].rstrip("]")
        full_title = item.text().split("[")[0].strip()
        thumbnail_url = item.data(Qt.UserRole)
        title, artist = self._parse_title(full_title)
        sanitized_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        threading.Thread(target=self.download_youtube_thread, args=(video_url, sanitized_title, title, artist, thumbnail_url), daemon=True).start()

    def download_youtube_thread(self, video_url, sanitized_title, title, artist, thumbnail_url):
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(self.download_dir, f"{sanitized_title}.%(ext)s"),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'ffmpeg_location': self.ffmpeg_path,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
            mp3_path = os.path.join(self.download_dir, f"{sanitized_title}.mp3")
            if os.path.exists(mp3_path):
                QApplication.postEvent(self, CustomEvent(f"Downloaded and added: {title}"))
                self.add_downloaded_song(mp3_path, title, artist, thumbnail_url, play_immediately=True)
            else:
                QApplication.postEvent(self, CustomEvent(f"Failed to find downloaded song: {title}"))
        except Exception as e:
            QApplication.postEvent(self, CustomEvent(f"Error downloading {title}: {str(e)}"))

    def add_downloaded_song(self, file_name, title, artist, thumbnail_url=None, play_immediately=False):
        self.playlist_songs.append(file_name)
        self.all_songs.append((file_name, title, artist, thumbnail_url))
        self.playlist.addItem(f"{artist} - {title}")
        if thumbnail_url:
            try:
                with urllib.request.urlopen(thumbnail_url) as response:
                    image_data = response.read()
                pixmap = QPixmap()
                pixmap.loadFromData(image_data)
                scaled_pixmap = pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.thumbnail_label.setPixmap(scaled_pixmap)
            except Exception:
                self.thumbnail_label.setText("No Image")
        else:
            self.thumbnail_label.setText("No Image")
        if play_immediately:
            self.current_song = file_name
            self.play_song()
        else:
            self.update_song_info()

    def add_song(self):
        file_names, _ = QFileDialog.getOpenFileNames(self, "Add MP3 Files", "", "MP3 Files (*.mp3)")
        for file_name in file_names:
            if file_name:
                self.playlist_songs.append(file_name)
                try:
                    song = MP3(file_name)
                    title = str(song.get("TIT2", os.path.basename(file_name)))
                    artist = str(song.get("TPE1", "Unknown Artist"))
                    self.all_songs.append((file_name, title, artist, None))
                    self.playlist.addItem(f"{artist} - {title}")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to add song: {str(e)}")
        if file_names and not self.is_playing:
            self.update_song_info()

    def open_song(self):
        file_names, _ = QFileDialog.getOpenFileNames(self, "Open MP3 Files", "", "MP3 Files (*.mp3)")
        first_song = None
        for file_name in file_names:
            if file_name:
                self.playlist_songs.append(file_name)
                try:
                    song = MP3(file_name)
                    title = str(song.get("TIT2", os.path.basename(file_name)))
                    artist = str(song.get("TPE1", "Unknown Artist"))
                    self.all_songs.append((file_name, title, artist, None))
                    self.playlist.addItem(f"{artist} - {title}")
                    if not first_song:
                        first_song = file_name
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to add song: {str(e)}")
        if first_song:
            self.current_song = first_song
            self.play_song()

    def play_song(self):
        if self.current_song and self.current_song in self.playlist_songs:
            try:
                pygame.mixer.music.load(self.current_song)
                pygame.mixer.music.set_volume(self.volume_slider.value() / 100)
                pygame.mixer.music.play(start=0)
                self.is_playing = True
                self.current_position = 0
                self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
                self.update_song_info()
            except pygame.error as e:
                QMessageBox.critical(self, "Error", f"Failed to play song: {str(e)}")
                self.stop()
        else:
            QMessageBox.warning(self, "Warning", "No song selected.")
            self.stop()

    def delete_song(self):
        selected_items = self.playlist.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            index = self.playlist.row(item)
            self.playlist.takeItem(index)
            removed_song = self.playlist_songs.pop(index)
            self.all_songs = [(path, title, artist, thumb) for path, title, artist, thumb in self.all_songs if path != removed_song]
        if self.current_song not in self.playlist_songs:
            self.current_song = None
            self.stop()
        else:
            self.update_song_info()

    def filter_songs(self):
        search_text = self.search_bar.text().lower()
        self.playlist.clear()
        self.playlist_songs.clear()
        for file_name, title, artist, thumbnail_url in self.all_songs:
            if search_text in title.lower() or search_text in artist.lower():
                self.playlist_songs.append(file_name)
                self.playlist.addItem(f"{artist} - {title}")
        if self.current_song not in self.playlist_songs:
            self.current_song = None
            self.stop()

    def play_pause(self):
        if self.playlist_songs:
            if not self.current_song or self.current_song not in self.playlist_songs:
                self.current_song = self.playlist_songs[0]
            if not self.is_playing:
                try:
                    pygame.mixer.music.load(self.current_song)
                    pygame.mixer.music.set_volume(self.volume_slider.value() / 100)
                    pygame.mixer.music.play(start=self.current_position)
                    self.is_playing = True
                    self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
                    self.update_song_info()
                except pygame.error as e:
                    QMessageBox.critical(self, "Error", f"Failed to play song: {str(e)}")
                    self.stop()
            else:
                pygame.mixer.music.pause()
                self.is_playing = False
                self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

    def stop(self):
        pygame.mixer.music.stop()
        self.is_playing = False
        self.current_position = 0
        self.seek_slider.setValue(0)
        self.current_time_label.setText("0:00")
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.thumbnail_label.setText("No Image")
        self.title_label.setText("No song selected")
        self.artist_label.setText("")

    def prev_song(self):
        if self.current_song and self.playlist_songs:
            index = self.playlist_songs.index(self.current_song)
            if index > 0:
                self.current_song = self.playlist_songs[index - 1]
                self.play_song()
            elif self.repeat_mode == "all":
                self.current_song = self.playlist_songs[-1]
                self.play_song()

    def next_song(self):
        if not self.playlist_songs:
            QMessageBox.warning(self, "Warning", "No songs in playlist.")
            return
        if not self.current_song or self.current_song not in self.playlist_songs:
            self.current_song = self.playlist_songs[0]
            self.play_song()
            return
        index = self.playlist_songs.index(self.current_song)
        if self.is_shuffle:
            # 무작위 재생 모드: 무작위로 다음 곡 선택
            new_index = random.randint(0, len(self.playlist_songs) - 1)
            while new_index == index and len(self.playlist_songs) > 1:
                new_index = random.randint(0, len(self.playlist_songs) - 1)
            self.current_song = self.playlist_songs[new_index]
            self.play_song()
        else:
            # Shuffle이 꺼져 있는 경우
            if index < len(self.playlist_songs) - 1:
                self.current_song = self.playlist_songs[index + 1]
                self.play_song()
            elif self.repeat_mode == "all":
                # 전체 반복 모드: 마지막 곡에서 첫 곡으로
                self.current_song = self.playlist_songs[0]
                self.play_song()
            else:
                # 반복 끄기 또는 한곡 반복: 마지막 곡이면 다음 곡 없음
                QMessageBox.warning(self, "Warning", "No next song available.")
                self.stop()

    def play_selected_song(self, item):
        index = self.playlist.row(item)
        self.current_song = self.playlist_songs[index]
        self.play_song()

    def update_song_info(self):
        if self.current_song:
            try:
                song = MP3(self.current_song)
                self.seek_slider.setMaximum(int(song.info.length))
                self.total_time_label.setText(self.format_time(song.info.length))
                for song_path, title, artist, thumbnail_url in self.all_songs:
                    if song_path == self.current_song:
                        self.title_label.setText(title)
                        self.artist_label.setText(artist)
                        if thumbnail_url:
                            try:
                                with urllib.request.urlopen(thumbnail_url) as response:
                                    image_data = response.read()
                                pixmap = QPixmap()
                                pixmap.loadFromData(image_data)
                                scaled_pixmap = pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                                self.thumbnail_label.setPixmap(scaled_pixmap)
                            except Exception:
                                self.thumbnail_label.setText("No Image")
                        else:
                            self.thumbnail_label.setText("No Image")
                        break
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load song metadata: {str(e)}")
                self.current_song = None
                self.stop()

    def set_volume(self):
        volume = self.volume_slider.value() / 100
        pygame.mixer.music.set_volume(volume)
        if volume > 0:
            self.volume_button.setIcon(self.style().standardIcon(QStyle.SP_MediaVolume))
            self.last_volume = self.volume_slider.value()
        else:
            self.volume_button.setIcon(self.style().standardIcon(QStyle.SP_MediaVolumeMuted))

    def start_seeking(self):
        self.is_seeking = True

    def stop_seeking(self):
        self.is_seeking = False
        position = self.seek_slider.value()
        if self.current_song:
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.load(self.current_song)
                pygame.mixer.music.set_volume(self.volume_slider.value() / 100)
                pygame.mixer.music.play(start=position)
                self.is_playing = True
                self.current_position = position
                self.current_time_label.setText(self.format_time(position))
                self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
            except pygame.error as e:
                QMessageBox.critical(self, "Error", f"Failed to seek song: {str(e)}")
                self.stop()

    def seek(self):
        if self.is_seeking:
            position = self.seek_slider.value()
            self.current_time_label.setText(self.format_time(position))

    def seek_relative(self, seconds):
        if self.current_song and self.is_playing:
            current_pos = self.current_position
            try:
                song_length = MP3(self.current_song).info.length
                new_pos = max(0, min(song_length, current_pos + seconds))
                pygame.mixer.music.stop()
                pygame.mixer.music.load(self.current_song)
                pygame.mixer.music.set_volume(self.volume_slider.value() / 100)
                pygame.mixer.music.play(start=new_pos)
                self.current_position = new_pos
                self.seek_slider.setValue(int(new_pos))
                self.current_time_label.setText(self.format_time(new_pos))
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to seek song: {str(e)}")
                self.stop()

    def format_time(self, seconds):
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes}:{seconds:02d}"

    def update_seek_slider(self):
        if self.is_playing and self.current_song and not self.is_seeking:
            position = pygame.mixer.music.get_pos() / 1000
            if position >= 0 and pygame.mixer.music.get_busy():
                self.current_position += 1
                self.seek_slider.setValue(int(self.current_position))
                self.current_time_label.setText(self.format_time(self.current_position))
            try:
                song = MP3(self.current_song)
                if self.current_position >= song.info.length:
                    if self.repeat_mode == "one":
                        pygame.mixer.music.stop()
                        pygame.mixer.music.load(self.current_song)
                        pygame.mixer.music.set_volume(self.volume_slider.value() / 100)
                        pygame.mixer.music.play(start=0)
                        self.current_position = 0
                    elif self.repeat_mode == "all":
                        self.next_song()
                    elif self.is_shuffle:
                        self.next_song()
                    else:  # repeat_mode == "off"
                        index = self.playlist_songs.index(self.current_song) if self.current_song in self.playlist_songs else -1
                        if index < len(self.playlist_songs) - 1:
                            self.next_song()
                        else:
                            self.stop()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to check song duration: {str(e)}")
                self.stop()

    def update_playlist_order(self):
        new_order = []
        new_all_songs = []
        for i in range(self.playlist.count()):
            item = self.playlist.item(i)
            for song_path, title, artist, thumbnail_url in self.all_songs:
                if f"{artist} - {title}" == item.text():
                    new_order.append(song_path)
                    new_all_songs.append((song_path, title, artist, thumbnail_url))
                    break
        self.playlist_songs = new_order
        self.all_songs = new_all_songs

    def cycle_repeat_mode(self):
        if self.repeat_mode == "off":
            self.repeat_mode = "one"
            self.previous_repeat_mode = "one"
            self.repeat_action.setText("한곡 반복")
            self.repeat_button.setIcon(QIcon("images/repeat_one.png"))
        elif self.repeat_mode == "one":
            self.repeat_mode = "all"
            self.previous_repeat_mode = "all"
            self.repeat_action.setText("전체 반복")
            self.repeat_button.setIcon(QIcon("images/repeat_all.png"))
        else:
            self.repeat_mode = "off"
            self.previous_repeat_mode = "off"
            self.repeat_action.setText("반복 끄기")
            self.repeat_button.setIcon(QIcon("images/repeat_off.png"))

    def toggle_shuffle(self):
        self.is_shuffle = not self.is_shuffle
        if self.is_shuffle:
            self.previous_repeat_mode = self.repeat_mode  # Shuffle 활성화 전 반복 모드 저장
            self.repeat_mode = "off"  # Shuffle 중에는 반복 비활성화
            self.repeat_action.setText("무작위 재생")
            self.repeat_button.setIcon(QIcon("images/shuffle.png"))
        else:
            self.repeat_mode = self.previous_repeat_mode  # Shuffle 해제 시 이전 반복 모드 복원
            if self.repeat_mode == "off":
                self.repeat_action.setText("반복 끄기")
                self.repeat_button.setIcon(QIcon("images/repeat_off.png"))
            elif self.repeat_mode == "one":
                self.repeat_action.setText("한곡 반복")
                self.repeat_button.setIcon(QIcon("images/repeat_one.png"))
            else:  # self.repeat_mode == "all"
                self.repeat_action.setText("전체 반복")
                self.repeat_button.setIcon(QIcon("images/repeat_all.png"))

    def adjust_volume(self, delta):
        current_volume = self.volume_slider.value()
        new_volume = max(0, min(100, current_volume + delta))
        self.volume_slider.setValue(new_volume)

    def toggle_mute(self):
        if self.volume_slider.value() > 0:
            self.last_volume = self.volume_slider.value()
            self.volume_slider.setValue(0)
            self.volume_button.setIcon(self.style().standardIcon(QStyle.SP_MediaVolumeMuted))
        else:
            self.volume_slider.setValue(self.last_volume)
            self.volume_button.setIcon(self.style().standardIcon(QStyle.SP_MediaVolume))

    def show_about(self):
        QMessageBox.about(self, "About", "AlSong Style MP3 Player\nVersion 1.0\nBuilt with PyQt5 and pygame\nYouTube integration added")

    def customEvent(self, event):
        if hasattr(event, 'message'):
            QMessageBox.information(self, "Download Status", event.message)

class CustomEvent(QEvent):
    def __init__(self, message):
        super().__init__(QEvent.Type.User)
        self.message = message

if __name__ == '__main__':
    app = QApplication(sys.argv)
    player = MP3Player()
    player.show()
    sys.exit(app.exec_())