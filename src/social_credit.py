import time
import json

with open("social_cred.json", "w") as f:
  json.dump(scores, f)

with open("social_cred.json", "r") as f:
  scores = json.load(f)

print("SOCIAL CREDITS LOADED")
