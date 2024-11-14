import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
from rich.console import Console
from rich.table import Table
import re
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Event:
    name: str
    date: str
    category: str
    source: str
    description: Optional[str] = None

class MultiSourceEventsScraper:
    def __init__(self):
        self.console = Console()
        self.events = []
        self.sources = {
            "york": "https://registrar.yorku.ca/enrol/dates/religious-accommodation-resource-2024-2025",
            "ontario": "https://www.ontario.ca/page/ontarios-celebrations-and-commemorations"
        }

    def fetch_page(self, url: str) -> str:
        """Fetch webpage content with error handling."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching {url}: {str(e)}")
            return ""

    def parse_york_dates(self, date_text: str) -> str:
        """Parse York University date formats."""
        # Handle date ranges
        if "Begins at sunset on" in date_text:
            matches = re.findall(r"([A-Za-z]+\. \d+, \d{4})", date_text)
            if matches:
                return f"{matches[0]} - {matches[-1]}"
        # Handle single dates
        elif ", 2024" in date_text or ", 2025" in date_text:
            match = re.search(r"([A-Za-z]+\. \d+, \d{4})", date_text)
            if match:
                return match.group(1)
        return date_text

    def parse_ontario_dates(self, text: str) -> str:
        """Parse Ontario government date formats."""
        # Handle specific dates
        if re.search(r"[A-Za-z]+ \d+", text):
            return text
        # Handle months
        if re.match(r"^[A-Za-z]+$", text):
            return text
        return text

    def scrape_york_events(self, html_content: str):
        """Scrape events from York University page."""
        soup = BeautifulSoup(html_content, 'html.parser')
        table = soup.find('table')
        
        if not table:
            return

        rows = table.find_all('tr')[1:]  # Skip header row
        for row in rows:
            cols = row.find_all(['td'])
            if len(cols) == 2:
                name_text = cols[0].text.strip()
                # Extract religion from parentheses if present
                religion = ""
                if "(" in name_text and ")" in name_text:
                    name = name_text[:name_text.find("(")].strip()
                    religion = name_text[name_text.find("(")+1:name_text.find(")")].strip()
                else:
                    name = name_text
                    
                event = Event(
                    name=name,
                    date=self.parse_york_dates(cols[1].text.strip()),
                    category=religion if religion else "Religious/Cultural",
                    source="York University",
                    description=cols[1].text.strip()
                )
                self.events.append(event)

    def scrape_ontario_events(self, html_content: str):
        """Scrape events from Ontario government page."""
        soup = BeautifulSoup(html_content, 'html.parser')
        months_section = soup.find_all('div', class_='medium-4 columns')
        
        for section in months_section:
            month_header = section.find('h3')
            if not month_header:
                continue
                
            month = month_header.text.strip()
            events_list = section.find('ul')
            if not events_list:
                continue
                
            for event in events_list.find_all('li'):
                event_text = event.text.strip()
                link = event.find('a')
                
                # Extract date if present (after dash)
                name = link.text.strip() if link else event_text
                date = ""
                if "–" in event_text:
                    name, date = event_text.split("–", 1)
                    name = name.strip()
                    date = date.strip()
                
                event = Event(
                    name=name,
                    date=date if date else month,
                    category="Provincial Celebration/Commemoration",
                    source="Ontario Government",
                    description=event_text
                )
                self.events.append(event)

    def display_events(self):
        """Display events in a formatted table."""
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Event Name")
        table.add_column("Date")
        table.add_column("Category")
        table.add_column("Source")
        table.add_column("Description", width=40)

        for event in sorted(self.events, key=lambda x: x.name):
            table.add_row(
                event.name,
                event.date,
                event.category,
                event.source,
                (event.description[:37] + "...") if event.description and len(event.description) > 40 else (event.description or "")
            )

        self.console.print(table)

    def save_to_json(self, filename='events.json'):
        """Save events to a JSON file."""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump([event.__dict__ for event in self.events], f, indent=2, ensure_ascii=False)
        print(f"Saved {len(self.events)} events to {filename}")

    def run(self):
        """Run the scraper for all sources."""
        # Scrape York University events
        york_content = self.fetch_page(self.sources["york"])
        if york_content:
            self.scrape_york_events(york_content)
            
        # Scrape Ontario government events
        ontario_content = self.fetch_page(self.sources["ontario"])
        if ontario_content:
            self.scrape_ontario_events(ontario_content)
            
        self.display_events()
        self.save_to_json()

def main():
    scraper = MultiSourceEventsScraper()
    scraper.run()

if __name__ == "__main__":
    main()