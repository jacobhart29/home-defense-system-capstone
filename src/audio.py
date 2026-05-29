import os
import time
import pygame

CHANNEL = None
FOLDER_PATH = ""
SUPPORTED_EXTENSIONS = (".wav", ".mp3", ".ogg")


def init_audio(PATH):
    global CHANNEL, FOLDER_PATH
    pygame.mixer.init()
    CHANNEL = pygame.mixer.Channel(0)
    FOLDER_PATH = PATH


def list_sounds():
    if not os.path.exists(FOLDER_PATH):
        return []

    AUDIO_FILES = [
        f
        for f in os.listdir(FOLDER_PATH)
        if f.lower().endswith(SUPPORTED_EXTENSIONS)
    ]
    return sorted(AUDIO_FILES)


def play(FILENAME):
    FULL_PATH = os.path.join(FOLDER_PATH, FILENAME)

    if not os.path.exists(FULL_PATH):
        return

    try:
        SOUND = pygame.mixer.Sound(FULL_PATH)
        CHANNEL.play(SOUND)
    except Exception:
        pass


def stop():
    if CHANNEL and CHANNEL.get_busy():
        CHANNEL.stop()
