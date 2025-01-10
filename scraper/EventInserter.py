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
            "Ascension of the Bahá'u'lláh", "Declaration of the Báb", 
            "Martyrdom of the Báb", "Ridván Festival"
        ],
        "default_description": "A Bahá'í observance that marks significant events in the history of the faith."
    },
    "Buddhism": {
        "events": [
            "Asalha Puja", "Bodhi Day", "Festival of Higan-e", 
            "Festival of Ksitigarbha", 
            "Magha Puja", "Mahāyāna New Year", 
            "Nirvana Day", "Pavarana", "Nyepi", 
            "Theravada New Year", 
            "Vesak",
        ],
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
    },
    "Hinduism": {
        "events": [
            "Dassehra", "Diwali", "Ganesh Chaturthi", "Hanuman Jayanti", 
            "Holi", "Krishna Janmashtami", "Lohri", "Makar Sankranti", 
            "Mahashivaratri", "Navaratri", "Hindu New Year", "Raksha Bandhan", 
            "Ramanavami", "Vasant Panchami", 
            
        ],
    },
    "Islam": {
        "events": [
            "Arbaeen", "Āshūrā", "Day of Ḥajj", "Eid-al-Fitr", 
            "Eid-al-Adha", "Hajj Pilgrimage", "Islamic New Year", 
            "Laylat al-Baraat", "Laylat al-Mi'rāj", "Laylat al-Qadr", 
            "Mawlid al-Nabīy", "Mawlid al-Nabi", "Ramadan"
        ],
    },
    "Judaism": {
        "events": [
            "Hanukkah", "Passover", "Purim", "Rosh Hashanah", 
            "Shavuot", "Shemini Atzeret", "Simchat Torah", 
            "Sukkot", "Tisha B'av", "Tu B'Shevat", "Yom Kippur"
        ],
    },
    "Sikhism": {
        "events": [
            "Bandi Chhor Divas", "Guru Har Rai Jayanti", 
            "Guru Nanak Jayanti", "Guru Gobind Singh Ji Jayanti", 
            "Hola Mohalla", 
            "Lohri", "Martyrdom of Guru Arjan Dev Sahib",
            "Martyrdom of Guru Tegh Bahadur Sahib", "Vaisakhi"
        ],
    },
    "Zoroastrianism": {
        "events": [
            "Jashne Sadeh"
        ],
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
    },
    "Week-Long Observances": {
        "events": [
            "16 Days of Activism Against Gender Violence",
            "Gender Equality Week", "Mennonite Heritage Week",
            "Public Service Pride Week", "Veterans' Week"
        ],
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
    },
    "Cultural Observances": {
        "events": [
            "4shanbe Souri", "Chinese New Year", "Kwanzaa", 
            "Le Réveillon de Noël", "Saint Lucy's Day", "Lunar New Year", 
            "Mid-Autumn Festival", "Midsummer", "Nowruz", 
            "Pride Weekend", "Shogatsu/Gantan-sai", "St. Patrick's Day", 
            "Thanksgiving", "Yalda"
        ],
    }
}

ALTERNATE_NAMES = {
    # Bahá'í Faith
    "Ridván Festival": ["The Most Great Festival", "King of Festivals", "Festival of Paradise", "Ridvan Festival", "ridvan festival", "ridvan"],
    "Declaration of the Báb": ["Day of the Báb", "declaration of the bab", "Declaration", "declaration"],
    "Ascension of Bahá'u'lláh": ["Day of Covenant", "ascension of bahaullah", "Ascension", "ascension"],
    "Birth of the Báb": ["birth of the bab", "Birth", "birth"],
    "Birth of Bahá'u'lláh": ["birth of bahaullah", "Birth", "birth"],
    "Martyrdom of the Báb": ["martyrdom of the bab", "Martyrdom", "martyrdom"],
    "Lucia Day":["Saint Lucy's Day, St. Lucy's day, Saint Lucys day, St. Lucys day"],
    
    # Buddhist
    "Vesak": ["Buddha Day", "Buddha Purnima", "Buddha Jayanti", "Wesak", "Vesākha", "Buddha's Birthday", "vesak"],
    "Māgha Pūjā Day": ["Magha Puja", "Sangha Day", "Fourfold Assembly Day", "magha puja day", "magha puja"],
    "Full Moon Days": ["Uposatha", "Observance Days", "full moon days", "full moon"],
    "Bodhi Day": ["bodhi day", "bodhi"],
    "Festival of Higan-e": ["Higan-e", "higan e", "higan"],
    "Mahāyāna New Year": ["Mahayana New Year", "mahayana new year", "mahayana"],
    "Nirvana Day": ["Parinirvana Day", "nirvana day", "nirvana"],
    "Pavarana Day": ["pavarana day", "pavarana"],
    "Saka New Year": ["Nyepi", "saka new year", "saka"],
    "Vassa": ["Buddhist Lent", "vassa"],
    
    # Christianity
    "Christmas": ["Christmas Day", "Christmas Eve", "Nativity of Jesus", "Nativity of the Lord", "Feast of the Nativity", "christmas"],
    "Easter": ["Easter Sunday", "Easter Day", "Resurrection Sunday", "Paschal Sunday", "Pascha", "easter"],
    "Epiphany": ["Three Kings Day", "Dia de los Reyes", "Theophany", "Little Christmas", "epiphany"],
    "Pentecost": ["Whitsunday", "Whit Sunday", "Sunday of the Holy Spirit", "pentecost"],
    "Advent": ["Nativity Fast", "Little Lent", "Winter Lent", "advent"],
    "Good Friday": ["Holy Friday", "Great Friday", "Black Friday", "good friday"],
    "Holy Thursday": ["Maundy Thursday", "Great Thursday", "Covenant Thursday", "holy thursday"],
    "Ash Wednesday": ["ash wednesday"],
    "Feast of the Nativity": ["Christmas", "feast of the nativity", "nativity"],
    "Ascension": ["Ascension Day", "ascension day", "ascension"],
    "Feast of Mary Mother of God": ["Solemnity of Mary", "feast of mary", "mary mother"],
    "Feast of St. Basil": ["Saint Basil's Day", "feast of st basil", "st basil"],
    "Feast Day of the Epiphany": ["Epiphany", "feast of epiphany", "epiphany"],
    "Palm Sunday": ["palm sunday"],
    "Shrove Tuesday": ["Pancake Tuesday", "Mardi Gras", "shrove tuesday", "shrove"],
    "Lent": ["lent"],
    
    # Hindu
    "Diwali": ["Deepavali", "Festival of Lights", "Deepawali", "Dipavali", "diwali"],
    "Mahashivaratri": ["Maha Shivaratri", "Great Night of Shiva", "Shivaratri", "mahashivaratri", "shivaratri"],
    "Krishna Janmashtami": ["Janmashtami", "Gokulashtami", "Krishna Jayanti", "janmashtami", "krishna jayanti"],
    "Ganesh Chaturthi": ["Vinayaka Chaturthi", "Ganeshotsav", "Vinayaka Chavithi", "ganesh chaturthi", "ganesh"],
    "Navaratri": ["Navratri", "Durga Puja", "Navratra", "Nine Nights", "navaratri"],
    "Dassehra": ["Dussehra", "Vijayadashami", "Dasara", "Dashain", "dassehra"],
    "Holi": ["Festival of Colors", "Spring Festival", "Phagwah", "holi"],
    "Makar Sankranti": ["Maghi", "Pongal", "makar sankranti", "sankranti"],
    "Hanuman Jayanti": ["hanuman jayanti", "hanuman"],
    "Lohri": ["lohri"],
    "Navvarsha": ["Hindu New Year", "Vikram New Year", "Vikram Samvat New Year", "navvarsha"],
    "Raksha Bandhan": ["Rakhi", "raksha bandhan", "rakhi"],
    "Ramanavami": ["Ram Navami", "ramanavami", "ram navami"],
    "Vasanta Panchami": ["Vasant Panchami", "Saraswati Puja", "vasanta panchami", "vasant"],
    
    # Islamic
    "Eid al-Fitr": ["ʻĪd al-Fiṭr", "Eid ul-Fitr", "Ramadan Eid", "Lesser Eid", "Sweet Eid", "eid al fitr", "eid"],
    "Eid al-Adha": ["ʻĪd al-'Aḍḥá", "Eid ul-Adha", "Bakrid", "Greater Eid", "Sacrifice Feast", "eid al adha", "eid"],
    "Ramadan": ["Ramazan", "Ramzan", "Month of Fasting", "Month of Mercy", "ramadan"],
    "Islamic New Year": ["Hijri New Year", "Arabic New Year", "Muharram", "Ras as-Sanah al-Hijriyah", "islamic new year"],
    "Āshūrā": ["Ashura", "Yawm Ashura", "Day of Ashura", "The Tenth", "ashura"],
    "Mawlid al-Nabīy": ["Mawlid", "Milad un Nabi", "Prophet's Birthday", "Eid al-Mawlid", "mawlid al nabiy", "mawlid"],
    "Laylat al-Qadr": ["Night of Power", "Night of Decree", "laylat al qadr", "laylat"],
    "Laylat al-Mi'rāj": ["Night Journey", "laylat al miraj", "miraj"],
    "Arbaeen": ["Chehlum", "arbaeen"],
    "Day of Ḥajj": ["Day of Hajj", "day of hajj", "hajj"],
    
    # Jewish
    "Passover": ["Pesach", "Festival of Unleavened Bread", "Pesah", "Feast of Liberation", "passover"],
    "Rosh Hashanah": ["Jewish New Year", "Head of the Year", "Yom Teruah", "rosh hashanah"],
    "Yom Kippur": ["Day of Atonement", "Holiest Day of the Year", "yom kippur"],
    "Sukkot": ["Feast of Tabernacles", "Feast of Booths", "Succot", "Festival of Ingathering", "sukkot"],
    "Shemini Atzeret": ["Eighth Day of Assembly", "Festival of the Eighth Day", "shemini atzeret"],
    "Simchat Torah": ["Rejoicing with the Torah", "Joy of the Torah", "simchat torah"],
    "Hanukkah": ["Chanukah", "Festival of Lights", "Feast of Dedication", "hanukkah"],
    "Shavuot": ["Feast of Weeks", "Pentecost", "Festival of First Fruits", "shavuot"],
    "Tisha B'av": ["Ninth of Av", "The Ninth of Av", "Day of Destruction", "tisha bav"],
    "Purim": ["Feast of Lots", "purim"],
    "Tu BiShvat": ["New Year of the Trees", "tu bishvat","Tu B'Shevat", "tu bshevat"],
    
    # Sikh
    "Vaisakhi": ["Baisakhi", "Vaisakhdi", "Khalsa Day", "Sikh New Year", "vaisakhi"],
    "Bandi Chhor Divas": ["Bandi Shor Divas", "Prison Release Day", "Day of Liberation", "bandi chhor divas"],
    "Birth of Guru Nanak Dev Ji": ["Guru Nanak Gurpurab", "Guru Nanak's Prakash Utsav", "birth of guru nanak dev ji"],
    "Birth of Guru Har Rai": ["birth of guru har rai"],
    "Birth date of Guru Gobind Singh Ji": ["birth of guru gobind singh ji"],
    "Hola Mohalla": ["Hola", "hola mohalla"],
    "Installation of Sri Guru Granth Sahib Ji": ["installation of guru granth sahib"],
    "Lohri": ["lohri"],
    "Martyrdom of Guru Arjan Dev Sahib": ["martyrdom of guru arjan dev"],
    "Martyrdom of Guru Tegh Bahadur Sahib": ["martyrdom of guru tegh bahadur"],
    
    # Zoroastrianism
    "Jashne Sadeh": ["Jashn-e Sadeh", "Festival of Fire", "jashne sadeh", "sadeh"],
    
    # Cultural
    "Nowruz": ["Norooz", "Persian New Year", "Iranian New Year", "Spring Festival", "nowruz"],
    "Lunar New Year": ["Chinese New Year", "Spring Festival", "Tết", "Seollal", "lunar new year"],
    "Shogatsu/Gantan-sai": ["Japanese New Year", "shogatsu", "gantan sai"],
    "Chaharshanbe Suri": ["Festival of Fire", "4shanbe Souri"],
    "Mid-Autumn Festival": ["Moon Festival", "Mooncake Festival", "mid autumn festival"],
    "Kwanzaa": ["kwanzaa"],
    "Pride Weekend": ["Pride Festival", "pride weekend", "pride"],
    "St. Patrick's Day": ["Saint Patrick's Day", "st patricks day"],
    "Yalda": ["Shab-e Yalda", "Yalda Night", "yalda"],
    
    # Month-Long Observances
    "Pride Season": ["Pride Month", "LGBTQ+ Pride Month", "Gay Pride Month", "pride season", "pride"],
    "National Indigenous History Month": ["Aboriginal History Month", "First Peoples History Month", "national indigenous history month", "indigenous history"],
    "Asian Heritage Month": ["Asian American and Pacific Islander Heritage Month", "AAPI Heritage Month", "asian heritage month"],
    "Black History Month": ["African American History Month", "African Heritage Month", "black history month"],
    "Tamil Heritage Month": ["tamil heritage month", "tamil"],
    "Jewish Heritage Month": ["jewish heritage month"],
    "Filipino Heritage Month": ["filipino heritage month", "filipino"],
    "Italian Heritage Month": ["italian heritage month", "italian"],
    "German Heritage Month": ["german heritage month", "german"],
    "Polish Heritage Month": ["polish heritage month", "polish"],
    
    # International/National Days
    "National Day for Truth and Reconciliation": ["Orange Shirt Day", "Day for Truth and Reconciliation", "national day for truth and reconciliation"],
    "National Indigenous Languages Day": ["Aboriginal Languages Day", "First Nations Languages Day", "national indigenous languages day"],
    "International Holocaust Remembrance Day": ["Holocaust Remembrance Day", "international holocaust remembrance day"],
    "International Day of the Girl Child": ["Day of the Girl", "international day of the girl"],
    "International Mother Language Day": ["Mother Language Day", "mother language day"],
    "International Women's Day": ["IWD", "womens day", "international womens day"],
    
    # Other Important Days
    "Canada Day": ["Dominion Day", "canada day"],
    "Commonwealth Day": ["commonwealth day"],
    "Family Day": ["family day"],
    "Remembrance Day": ["Armistice Day", "remembrance day"],
    "Victoria Day": ["May Two-Four", "victoria day"],
    "National Acadian Day": ["acadian day", "acadian"],
    "Saint-Jean-Baptiste Day": ["St Jean Baptiste", "saint jean baptiste"]
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