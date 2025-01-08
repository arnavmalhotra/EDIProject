import os
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
import pytz

# Load environment variables
load_dotenv()

# Initialize MongoDB connection
MONGO_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URI)
db = client.events_db
events_collection = db.events

EVENTS_DATA = {
    "Bahá'í Faith": {
        "events": [
            "Ascension of Bahá'u'lláh", "Declaration of the Báb", 
            "Martyrdom of the Báb", "Ridván Festival"
        ],
        "default_description": "A Bahá'í observance that marks significant events in the history of the faith."
    },
    "Buddhism": {
        "events": [
            "Asalha Puja", "Bodhi Day", "Festival of Higan-e", 
            "Festival of Ksitigarbha (Jizo) Bodhisattva", "Full Moon Days", 
            "Magha Puja", "Māgha Pūjā Day", "Mahāyāna New Year", 
            "Nirvana Day", "Pavarana Day", "Saka New Year", 
            "Spring Ohigan", "Theravāda New Year", "Vassa", 
            "Vesak", "Wesak"
        ],
        "default_description": "An important Buddhist observance that promotes spiritual growth and mindfulness."
    },
    "Christianity": {
        "events": [
            "Advent", "All Saints Day", "Ascension", "Ash Wednesday", 
            "Christmas", "Christmas Eve", "Easter", "Epiphany", 
            "Feast of Mary Mother of God", "Feast of St. Basil", 
            "Feast Day of the Epiphany", "Feast of the Nativity", 
            "Good Friday", "Holy Thursday", "Lent", "Orthodox Easter", 
            "Orthodox Good Friday", "Palm Sunday", "Pentecost", 
            "Shrove Tuesday", "Theophany"
        ],
        "default_description": "A significant Christian observance that holds deep spiritual meaning for followers of the faith."
    },
    "Hinduism": {
        "events": [
            "Dassehra", "Diwali", "Ganesh Chaturthi", "Hanuman Jayanti", 
            "Holi", "Krishna Janmashtami", "Lohri", "Makar Sankranti", 
            "Mahashivaratri", "Navaratri", "Navvarsha", "Raksha Bandhan", 
            "Ramanavami", "Sri Krishna Jayanti", "Vasanta Panchami", 
            "Vikram New Year"
        ],
        "default_description": "A Hindu festival that celebrates spiritual traditions and cultural heritage."
    },
    "Islam": {
        "events": [
            "Arbaeen", "Āshūrā", "Day of Ḥajj", "Eid al-Fitr", 
            "Eid al-Adha", "Hajj Pilgrimage", "Islamic New Year", 
            "Laylat al-Baraat", "Laylat al-Mi'rāj", "Laylat al-Qadr", 
            "Mawlid al-Nabīy", "Mawlid al-Nabi", "Ramadan"
        ],
        "default_description": "An Islamic observance that holds special significance in the Muslim faith."
    },
    "Judaism": {
        "events": [
            "Hanukkah", "Passover", "Purim", "Rosh Hashanah", 
            "Shavuot", "Shemini Atzeret", "Simchat Torah", 
            "Sukkot", "Tisha B'av", "Tu BiShvat", "Yom Kippur"
        ],
        "default_description": "A Jewish holiday that commemorates important events and traditions in Jewish history and faith."
    },
    "Sikhism": {
        "events": [
            "Bandi Chhor Divas", "Birth of Guru Har Rai", 
            "Birth of Guru Nanak Dev Ji", "Birth date of Guru Gobind Singh Ji", 
            "Hola Mohalla", "Installation of Sri Guru Granth Sahib Ji", 
            "Lohri", "Martyrdom of Guru Arjan Dev Sahib",
            "Martyrdom of Guru Tegh Bahadur Sahib", "Vaisakhi"
        ],
        "default_description": "A Sikh observance that commemorates important events and figures in Sikh history."
    },
    "Zoroastrianism": {
        "events": [
            "Jashne Sadeh"
        ],
        "default_description": "A Zoroastrian observance that celebrates ancient Persian traditions and spiritual beliefs."
    },
    "Month-Long Observances": {
        "events": [
            "Asian Heritage Month", "Black History Month", 
            "Canadian Islamic History Month", "Canadian Jewish Heritage Month",
            "Filipino Heritage Month", "Genocide Remembrance, Condemnation and Prevention Month",
            "German Heritage Month", "Hindu Heritage Month", "Irish Heritage Month",
            "Italian Heritage Month", "Latin American Heritage Month",
            "Lebanese Heritage Month", "National Indigenous History Month",
            "Polish Heritage Month", "Portuguese Heritage Month",
            "Pride Season", "Sikh Heritage Month", "Tamil Heritage Month",
            "Women's History Month"
        ],
        "default_description": "A month dedicated to celebrating and recognizing the contributions and heritage of various communities."
    },
    "Week-Long Observances": {
        "events": [
            "16 Days of Activism Against Gender Violence",
            "Gender Equality Week", "Mennonite Heritage Week",
            "Public Service Pride Week", "Veterans' Week"
        ],
        "default_description": "A week dedicated to raising awareness and taking action on specific issues."
    },
    "International Days": {
        "events": [
            "International Day Against Homophobia, Transphobia and Biphobia",
            "International Day for African and Afrodescendant Culture",
            "International Day for Elimination of Racial Discrimination",
            "International Day for Persons with Disabilities",
            "International Day of the Girl Child",
            "International Day to Combat Islamophobia",
            "International Holocaust Remembrance Day",
            "International Mother Language Day",
            "International Transgender Day of Visibility",
            "International Women's Day"
        ],
        "default_description": "An international observance that promotes awareness and action on global issues."
    },
    "National Days": {
        "events": [
            "Anniversary of Statute of Westminster",
            "Battle of Vimy Ridge Anniversary", "British Home Child Day", 
            "Canada Day", "Canadian Multiculturalism Day", 
            "Commonwealth Day", "Day of Commemoration of the Great Upheaval",
            "Dutch Heritage Day", "Emancipation Day", "Family Day",
            "Human Rights Day", "Indigenous Veterans Day",
            "Lincoln Alexander Day", "National Acadian Day",
            "National Child Day", "National Day for Truth and Reconciliation",
            "National Day of Remembrance and Action on Violence Against Women",
            "National Day of Remembrance for Victims of Air Disasters",
            "National Day of Remembrance for Victims of Terrorism",
            "National Day of Remembrance of Quebec City Mosque Attack",
            "National Flag of Canada Day", "National Indigenous Languages Day",
            "National Indigenous Peoples Day", "National Seniors Day",
            "Persons Day", "Raoul Wallenberg Day", "Remembrance Day",
            "Saint-Jean-Baptiste Day", "Sir John A. Macdonald Day",
            "Victoria Day"
        ],
        "default_description": "A national observance that commemorates significant events and people in Canadian history."
    },
    "Cultural Observances": {
        "events": [
            "4shanbe Souri", "Chinese New Year", "Kwanzaa", 
            "Le Réveillon de Noël", "Lucia Day", "Lunar New Year", 
            "Mid-Autumn Festival", "Midsummer", "Nowruz", 
            "Pride Weekend", "Shogatsu/Gantan-sai", "St. Patrick's Day", 
            "Thanksgiving", "Yalda"
        ],
        "default_description": "A cultural celebration that reflects community traditions and heritage."
    }
}

ALTERNATE_NAMES = {
    # Bahá'í Faith
    "Ridván Festival": ["The Most Great Festival", "King of Festivals", "Festival of Paradise"],
    "Declaration of the Báb": ["Day of the Báb"],
    "Ascension of Bahá'u'lláh": ["Day of Covenant"],
    
    # Buddhist
    "Vesak": ["Buddha Day", "Buddha Purnima", "Buddha Jayanti", "Wesak", "Vesākha", "Buddha's Birthday"],
    "Māgha Pūjā Day": ["Magha Puja", "Sangha Day", "Fourfold Assembly Day"],
    "Full Moon Days": ["Uposatha", "Observance Days"],
    
    # Christianity
    "Christmas": ["Christmas Day", "Christmas Eve", "Nativity of Jesus", "Nativity of the Lord", "Feast of the Nativity"],
    "Easter": ["Easter Sunday", "Easter Day", "Resurrection Sunday", "Paschal Sunday", "Pascha"],
    "Epiphany": ["Three Kings Day", "Dia de los Reyes", "Theophany", "Little Christmas"],
    "Pentecost": ["Whitsunday", "Whit Sunday", "Sunday of the Holy Spirit"],
    "Advent": ["Nativity Fast", "Little Lent", "Winter Lent"],
    "Good Friday": ["Holy Friday", "Great Friday", "Black Friday"],
    "Holy Thursday": ["Maundy Thursday", "Great Thursday", "Covenant Thursday"],
    
    # Hindu
    "Diwali": ["Deepavali", "Festival of Lights", "Deepawali", "Dipavali"],
    "Mahashivaratri": ["Maha Shivaratri", "Great Night of Shiva", "Shivaratri"],
    "Sri Krishna Jayanti": ["Janmashtami", "Krishna Janmashtami", "Gokulashtami", "Krishna Jayanti"],
    "Ganesh Chaturthi": ["Vinayaka Chaturthi", "Ganeshotsav", "Vinayaka Chavithi"],
    "Navaratri": ["Navratri", "Durga Puja", "Navratra", "Nine Nights"],
    "Dassehra": ["Dussehra", "Vijayadashami", "Dasara", "Dashain"],
    "Makar Sankranti": ["Pongal", "Lohri", "Magh Bihu", "Maghi"],
    "Holi": ["Festival of Colors", "Spring Festival", "Phagwah"],
    
    # Islamic
    "Eid al-Fitr": ["ʻĪd al-Fiṭr", "Eid ul-Fitr", "Ramadan Eid", "Lesser Eid", "Sweet Eid"],
    "Eid al-Adha": ["ʻĪd al-'Aḍḥá", "Eid ul-Adha", "Bakrid", "Greater Eid", "Sacrifice Feast"],
    "Ramadan": ["Ramazan", "Ramzan", "Month of Fasting", "Month of Mercy"],
    "Islamic New Year": ["Hijri New Year", "Arabic New Year", "Muharram", "Ras as-Sanah al-Hijriyah"],
    "Āshūrā": ["Ashura", "Yawm Ashura", "Day of Ashura", "The Tenth"],
    "Mawlid al-Nabīy": ["Mawlid", "Milad un Nabi", "Prophet's Birthday", "Eid al-Mawlid"],
    "Laylat al-Qadr": ["Night of Power", "Night of Decree", "Night of Destiny"],
    
    # Jewish
    "Passover": ["Pesach", "Festival of Unleavened Bread", "Pesah", "Feast of Liberation"],
    "Rosh Hashanah": ["Jewish New Year", "Head of the Year", "Yom Teruah"],
    "Yom Kippur": ["Day of Atonement", "Holiest Day of the Year"],
    "Sukkot": ["Feast of Tabernacles", "Feast of Booths", "Succot", "Festival of Ingathering"],
    "Shemini Atzeret": ["Eighth Day of Assembly", "Festival of the Eighth Day"],
    "Simchat Torah": ["Rejoicing with the Torah", "Joy of the Torah"],
    "Hanukkah": ["Chanukah", "Festival of Lights", "Feast of Dedication"],
    "Shavuot": ["Feast of Weeks", "Pentecost", "Festival of First Fruits"],
    "Tisha B'av": ["Ninth of Av", "The Ninth of Av", "Day of Destruction"],
    
    # Sikh
    "Vaisakhi": ["Baisakhi", "Vaisakhdi", "Khalsa Day", "Sikh New Year"],
    "Bandi Chhor Divas": ["Bandi Shor Divas", "Prison Release Day", "Day of Liberation"],
    "Birth of Guru Nanak Dev Ji": ["Guru Nanak Gurpurab", "Guru Nanak's Prakash Utsav"],
    "Martyrdom of Guru Tegh Bahadur Sahib": ["Shaheedi Guru Tegh Bahadur", "Martyrdom Day of Ninth Guru"],
    "Martyrdom of Guru Arjan Dev Sahib": ["Shaheedi Guru Arjan Dev Ji", "Martyrdom Day of Fifth Guru"],
    
    # Persian/Zoroastrian/Cultural
    "Nowruz": ["Norooz", "Persian New Year", "Iranian New Year", "Spring Festival"],
    "Jashne Sadeh": ["Jashn-e Sadeh", "Sadeh Festival", "Festival of Fire"],
    "4shanbe Souri": ["Chaharshanbe Suri", "Festival of Fire", "Red Wednesday"],
    "Lunar New Year": ["Chinese New Year", "Spring Festival", "Tết", "Seollal"],
    "Mid-Autumn Festival": ["Moon Festival", "Mooncake Festival", "Zhongqiu Festival", "Chuseok"],
    "Shogatsu/Gantan-sai": ["Japanese New Year", "Shōgatsu", "Oshōgatsu"],
    "Yalda": ["Shab-e Yalda", "Yalda Night", "Night of Forty"],
    "Kwanzaa": ["African American Heritage Week", "First Fruits"],
    
    # Month-Long Observances
    "Pride Season": ["Pride Month", "LGBTQ+ Pride Month", "Gay Pride Month"],
    "National Indigenous History Month": ["Aboriginal History Month", "First Peoples History Month"],
    "Asian Heritage Month": ["Asian American and Pacific Islander Heritage Month", "AAPI Heritage Month"],
    "Black History Month": ["African American History Month", "African Heritage Month"],
    
    # Week-Long Observances
    "Veterans' Week": ["Remembrance Week", "Week of Remembrance"],
    "16 Days of Activism Against Gender Violence": ["16 Days Campaign", "16 Days of Activism"],
    
    # International/National Days
    "International Mother Language Day": ["International Native Language Day"],
    "International Day of the Girl Child": ["Day of the Girl", "International Day of Girls"],
    "National Flag of Canada Day": ["Flag Day", "Canadian Flag Day"],
    "Dutch Heritage Day": ["Netherlands Heritage Day", "Dutch Canadian Heritage Day"],
    "National Indigenous Languages Day": ["Aboriginal Languages Day", "First Nations Languages Day"],
    "National Day for Truth and Reconciliation": ["Orange Shirt Day", "Day for Truth and Reconciliation"],
    "Family Day": ["Ontario Family Day", "Provincial Family Day", "Family Time"],
    "Saint-Jean-Baptiste Day": ["Fête nationale du Québec", "St. John the Baptist Day", "Quebec's National Holiday"]
}

def initialize_events():
    """Initialize events in the database with basic information."""
    print("\nStarting event initialization...")
    
    for category, data in EVENTS_DATA.items():
        print(f"\nProcessing category: {category}")
        
        for event_name in data["events"]:
            # Create the base event document
            event_doc = {
                "name": event_name,
                "category": category,
                "additional_details": data["default_description"],
                "image_url": f"/images/{event_name.lower().replace(' ', '_')}.jpg",
                "alternate_names": ALTERNATE_NAMES.get(event_name, []),
                "created_at": datetime.now(pytz.utc),
                "last_updated": datetime.now(pytz.utc),
                "source_urls": []
            }
            
            try:
                # Insert the event if it doesn't exist
                result = events_collection.update_one(
                    {"name": event_name},
                    {"$setOnInsert": event_doc},
                    upsert=True
                )
                
                if result.upserted_id:
                    print(f"✓ Inserted new event: {event_name}")
                else:
                    print(f"• Event already exists: {event_name}")
                    
            except Exception as e:
                print(f"✗ Error inserting event {event_name}: {e}")

def main():
    """Main execution function."""
    try:
        print("Connected to MongoDB successfully")
        initialize_events()
        print("\nEvent initialization completed successfully!")
        
    except Exception as e:
        print(f"\nError during initialization: {e}")
        
    finally:
        client.close()
        print("\nDatabase connection closed")

if __name__ == "__main__":
    main()