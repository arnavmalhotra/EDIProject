import google.generativeai as genai
import requests
import json
import re
import time

def get_website_html(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the website: {e}")
        return None

def clean_json_response(response_text):
    # Remove markdown code blocks if present
    cleaned_text = re.sub(r'```json\n', '', response_text)
    cleaned_text = re.sub(r'```', '', cleaned_text)
    
    # Ensure we have valid JSON
    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return None

def extract_events(urls):
    # Configure Gemini
    genai.configure(api_key="AIzaSyAisUoMJ1iJEZEd0mpr8AwLIz9H_o0Cvdw")
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    all_events = []
    
    for url in urls:
        print(f"Processing: {url}")
        html_content = get_website_html(url)
        
        if html_content:
            try:
                response = model.generate_content(f"""
                Here is the HTML content from a webpage.
                Extract all the events along with their dates from the html and return only JSON code of the events.
                The JSON should be formatted as such:
                                                  Name:
                                                  Start Date:
                                                  End Date: (The same as the start date in most cases)
                                                  Additional Details: (Null, if nothing is specified, otherwise return the specified details)
                Do not return anything other than the JSON code requested
                
                {html_content}
                """)
                
                # Clean and parse the response
                events_data = clean_json_response(response.text)
                if events_data:
                    if isinstance(events_data, list):
                        all_events.extend(events_data)
                    else:
                        all_events.append(events_data)
            
            except Exception as e:
                print(f"Error processing {url}: {e}")
        
        # Add a small delay between requests
        time.sleep(2)
    
    # Save all events to a JSON file
    try:
        with open('events.json', 'w', encoding='utf-8') as f:
            json.dump(all_events, f, indent=2, ensure_ascii=False)
        print("Events successfully saved to events.json")
    except Exception as e:
        print(f"Error saving to JSON file: {e}")
    
    return all_events

# Example usage
urls = [
    "https://registrar.yorku.ca/enrol/dates/religious-accommodation-resource-2024-2025",
    "https://www.canada.ca/en/canadian-heritage/services/important-commemorative-days.html",
    "https://www.ontario.ca/page/ontarios-celebrations-and-commemorations",
    # Add more URLs here
]

events = extract_events(urls)