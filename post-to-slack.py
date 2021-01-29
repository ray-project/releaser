import os
import sys
from datetime import datetime

import pytz
import requests
from dotenv import load_dotenv

current_time_pacific = (
    datetime.utcnow()
    .replace(tzinfo=pytz.utc)
    .astimezone(pytz.timezone("America/Los_Angeles"))
)

if not ((9 <= current_time_pacific.hour < 17) and (current_time_pacific.weekday() < 5)):
    print("Not in US pacific working hours, skipping...")
    sys.exit(0)

load_dotenv()

markdown_text = "Anyscale Session Status \n```\n" + sys.stdin.read() + "```\n"

slack_url = os.environ["SLACK_WEBHOOK"]
slack_channnel = os.environ.get("SLACK_CHANNEL_OVERRIDE", "#simon-bot-testing")

resp = requests.post(
    slack_url,
    json={
        "text": markdown_text,
        "channel": slack_channnel,
        "username": "Release Bot",
        "icon_emoji": ":rocket:",
    },
)
print(resp.status_code)
print(resp.text)
