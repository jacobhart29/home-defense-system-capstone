import time
import pygame
import os

# SOUND MIXER
pygame.mixer.init()

SOUND_FOLDER = "./sounds" # has to be changed to the path thingy
SUPPORTED_FORMATS = (".wav", ".mp3", ".ogg")

LOADED_SOUNDS = {}

if os.path.exists(SOUND_FOLDER):
  for filename in os.listdir(SOUND_FOLDER):
    if filename.lower().endswith(SUPPORTED_FORMATS):
      FILE_PATH = os.path.join(SOUND_FOLDER, filename)
      try:
        LOADED_SOUNDS[filename] = pygame.mixer.Sound(FILE_PATH)
        print(f"LOADED: {filename}")
      except Exception es e:
        print(f"ERROR LOADING: {filename}")
else:
    print("FOLDER NOT FOUND")

print(f"\nSOUNDS LOADED: {len(LOADED_SOUNDS)}")


def play_sound(file_name):
  if file_name in LOADED_SOUNDS:
    print(f"PLAYING {file_name})
