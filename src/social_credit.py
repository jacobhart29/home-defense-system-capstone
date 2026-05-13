import json
from pathlib import Path

SCORES_PATH = Path(__file__).resolve().parent.parent / 'config' / 'social_credit.json'

def load_scores():
    with open(SCORES_PATH, "r") as f:
        return json.load(f)

def save_scores(scores):
    with open(SCORES_PATH, "w") as f:
        json.dump(scores, f)

def add_credits(user_id, amount):
    scores = load_scores()
    scores[user_id] = scores.get(user_id, 0) + amount
    save_scores(scores)

def remove_credits(user_id, amount):
    scores = load_scores()
    scores[user_id] = scores.get(user_id, 0) - amount
    save_scores(scores)

print("SOCIAL CREDITS LOADED")
