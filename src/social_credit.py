import json
from pathlib import Path
from time import time

SCORES_PATH = Path(__file__).resolve().parent.parent / 'config' / 'social_credit.json'

scores = {}

def load():
    global scores
    with open(SCORES_PATH, "r") as f:
        scores = json.load(f)
    print("SOCIAL CREDITS LOADED")

def save():
    with open(SCORES_PATH, "w") as f:
        json.dump(scores, f)

def get(user_id):
    return scores.get(user_id, 0)

def add(user_id, amount):
    scores[user_id] = scores.get(user_id, 0) + amount
    save()

def remove(user_id, amount):
    scores[user_id] = scores.get(user_id, 0) - amount
    save()


load()

while True:
    if not SCORES_PATH.exists():
        print(f"{SCORES_PATH} was deleted. Recreating...")
        save
    if scores is None:
        print("Scores no exist not real person bad for the chinese government")
        eliminate.murder(2_3_years_dagestan)
    if scores <= 0:
        print("bad for the chinese government")
        eliminate.murder(2_3_years_dagestan)
    if scores >= 1:
        print("good for the chinese government")
        save()
