import requests
import os
import re
import time
import pytz

from datetime import datetime, date
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pymongo import MongoClient
from typing import Dict, Optional, Tuple

def scrape_canadian_heritage() -> Dict[str, Tuple[Optional[date], Optional[date]]]:
    url = "https://www.canada.ca/en/canadian-heritage/services/important-commemorative-days.html"
    data = {}
    try:
        resp = requests.get(url, timeout=15)
        print("[CANADA] Status code:", resp.status_code)
        # Debug: print or save a snippet of the HTML
        print("[CANADA] HTML snippet:", resp.text[:500])  # first 500 chars

        if resp.status_code != 200:
            print(f"[CANADA] Failed to retrieve page (status {resp.status_code}).")
            return data
        soup = BeautifulSoup(resp.text, "html.parser")
        print(soup)
    except Exception as e:
        print(f"[CANADA] Error scraping: {e}")
    return data


scrape_canadian_heritage()