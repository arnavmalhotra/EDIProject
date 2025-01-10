import os
from datetime import datetime
import pytz
from pymongo import MongoClient
from dotenv import load_dotenv
import requests
from PIL import Image
from io import BytesIO
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from urllib.parse import quote
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('image_download.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize database connection
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
IMAGE_SAVE_PATH = os.getenv('IMAGE_SAVE_PATH', r"C:\Users\Arnav\Desktop\Code\EDIProject\frontend\public\images")

# Validate environment variables
if not MONGODB_URI:
    raise ValueError("MONGODB_URI not found in environment variables")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def connect_to_mongodb():
    """Connect to MongoDB with retry logic."""
    try:
        client = MongoClient(MONGODB_URI)
        db = client.events_db
        events_collection = db.events
        # Test the connection
        client.admin.command('ping')
        logger.info("Connected successfully to MongoDB!")
        return client, events_collection
    except Exception as e:
        logger.error(f"Error connecting to MongoDB: {e}")
        raise

def setup_selenium():
    """Simplified Selenium setup with minimal options."""
    try:
        options = webdriver.ChromeOptions()
        options.add_argument('--headless=new')  # Use new headless mode
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        # Disable images to speed up loading
        prefs = {
            "profile.managed_default_content_settings.images": 2
        }
        options.add_experimental_option("prefs", prefs)
        
        logger.info("Setting up Chrome WebDriver...")
        service = webdriver.ChromeService()
        driver = webdriver.Chrome(options=options, service=service)
        driver.set_page_load_timeout(30)
        
        logger.info("Chrome WebDriver setup successful!")
        return driver
        
    except Exception as e:
        logger.error(f"Error setting up Chrome WebDriver: {e}")
        raise

def check_image_url(url, is_religious_event=False):
    """Verify if URL points to a suitable image with improved error handling."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.google.com/'
        }
        
        # First just check if URL is accessible
        response = requests.head(url, headers=headers, timeout=5)
        if response.status_code != 200:
            logger.debug(f"URL not accessible: {url[:100]}")
            return False
            
        # Then get the actual image
        response = requests.get(url, headers=headers, timeout=10)
        
        # Check content type
        content_type = response.headers.get('Content-Type', '').lower()
        if not any(img_type in content_type for img_type in ['image/jpeg', 'image/png', 'image/webp']):
            logger.debug(f"Invalid content type: {content_type}")
            return False
            
        # Check file size (between 5KB and 20MB)
        file_size = len(response.content)
        if file_size < 5 * 1024:  # 5KB
            logger.debug(f"Image too small: {file_size} bytes")
            return False
        if file_size > 20 * 1024 * 1024:  # 20MB
            logger.debug(f"Image too large: {file_size} bytes")
            return False
            
        # Check image properties
        try:
            img = Image.open(BytesIO(response.content))
        except Exception as e:
            logger.debug(f"Error opening image: {e}")
            return False
            
        # More lenient size requirements for religious content
        width, height = img.size
        min_size = 200 if is_religious_event else 400
        
        if width < min_size or height < min_size:
            logger.debug(f"Image dimensions too small: {width}x{height}")
            return False
            
        # Very lenient aspect ratio check
        aspect_ratio = width / height
        if aspect_ratio < 0.2 or aspect_ratio > 5.0:
            logger.debug(f"Extreme aspect ratio: {aspect_ratio:.2f}")
            return False
            
        return True
        
    except requests.exceptions.RequestException as e:
        logger.debug(f"Request error checking image URL: {e}")
        return False
    except Exception as e:
        logger.debug(f"Error checking image URL: {e}")
        return False

def generate_search_variations(event_name, category):
    """Generate different search variations for religious/cultural events."""
    variations = [
        event_name,  # Original name
        f"{category} {event_name}",  # Category + name
    ]
    
    # For Bahá'í specific events
    if "bahá'í" in category.lower():
        variations.extend([
            f"Bahá'í {event_name}",
            "Shrine of Bahá'u'lláh",  # Relevant landmark
            "Bahji Shrine",  # Another relevant landmark
            f"{event_name} celebration",
            f"{event_name} commemoration"
        ])
        
        # Remove apostrophes for better search results
        clean_name = event_name.replace("'", "")
        if clean_name != event_name:
            variations.append(clean_name)
    
    # For religious events in general
    if any(term in category.lower() for term in ['religion', 'faith', 'holy', 'sacred']):
        variations.extend([
            f"holy day {event_name}",
            f"religious observance {event_name}",
            f"{category} holy day",
            f"{event_name} celebration"
        ])
    
    # Remove duplicates while preserving order
    return list(dict.fromkeys(variations))

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=5, min=5, max=30),
    retry=retry_if_exception_type((TimeoutException, WebDriverException))
)
def search_google_images(query, is_religious_event=False):
    """Search for images using Google Image Search with a simplified, reliable approach."""
    driver = None
    try:
        search_query = quote(f"{query}")
        url = f"https://images.google.ca/search?q={search_query}&tbm=isch"
        
        logger.info(f"Initializing Google Image search for: {query}")
        driver = setup_selenium()
        
        logger.info("Navigating to Google Images...")
        driver.get(url)
        
        # Wait for page load
        time.sleep(5)
        
        # Simple approach: get all img elements
        logger.info("Looking for images...")
        images = driver.find_elements(By.TAG_NAME, "img")
        
        if not images:
            logger.warning("No images found on page")
            return None
            
        logger.info(f"Found {len(images)} images")
        
        # Filter out small thumbnails and icons
        valid_images = []
        for img in images:
            try:
                src = img.get_attribute('src')
                if src and src.startswith('http') and 'encrypted-tbn0' not in src:
                    valid_images.append(src)
            except:
                continue
                
        logger.info(f"Found {len(valid_images)} valid image URLs")
        
        # Try each valid image URL
        for img_url in valid_images[:10]:  # Try first 10 valid images
            try:
                logger.info(f"Checking image URL: {img_url[:100]}...")
                if check_image_url(img_url, is_religious_event):
                    return img_url
            except Exception as e:
                logger.error(f"Error checking image URL {img_url[:100]}: {e}")
                continue
        
        return None
        
    except Exception as e:
        logger.error(f"Error during Google Image search: {str(e)}")
        return None
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("Browser closed successfully")
            except Exception as e:
                logger.error(f"Error closing browser: {e}")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def search_wikimedia_commons(query, is_religious_event=False):
    """Search for Creative Commons images on Wikimedia Commons."""
    try:
        base_url = "https://commons.wikimedia.org/w/api.php"
        headers = {
            'User-Agent': 'EDIProjectImageDownloader/1.0 (educational project) Python/3.x'
        }
        
        # First try with the exact name
        params = {
            "action": "query",
            "format": "json",
            "list": "search",
            "srnamespace": "6",  # File namespace
            "srlimit": "5",  # Increased limit for better chances
            "srsearch": f'"{query}" filetype:bitmap'
        }
        
        response = requests.get(base_url, params=params, headers=headers)
        data = response.json()
        
        # If no results, try a more general search
        if not data.get("query", {}).get("search"):
            params["srsearch"] = f"{query} filetype:bitmap"
            response = requests.get(base_url, params=params, headers=headers)
            data = response.json()
        
        if "query" in data and data["query"]["search"]:
            # Try each result until we find a suitable image
            for result in data["query"]["search"]:
                file_title = result["title"].replace('File:', '')
                file_params = {
                    "action": "query",
                    "format": "json",
                    "prop": "imageinfo",
                    "titles": f"File:{file_title}",
                    "iiprop": "url"
                }
                
                file_response = requests.get(base_url, params=file_params, headers=headers)
                file_data = file_response.json()
                
                pages = file_data["query"]["pages"]
                page_id = next(iter(pages))
                image_url = pages[page_id]["imageinfo"][0]["url"]
                
                if check_image_url(image_url, is_religious_event):
                    return image_url
        
        return None
            
    except Exception as e:
        logger.error(f"Error searching Wikimedia Commons: {e}")
        return None

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def download_and_process_image(url, image_path):
    """Download, process, and save image with proper attribution."""
    try:
        # Create the directory if it doesn't exist
        if not os.path.exists(IMAGE_SAVE_PATH):
            os.makedirs(IMAGE_SAVE_PATH)
            
        filename = os.path.basename(image_path)
        filepath = os.path.join(IMAGE_SAVE_PATH, filename)
        
        logger.info(f"Downloading image from: {url}")
        logger.info(f"Saving to: {filepath}")
        
        headers = {
            'User-Agent': 'EDIProjectImageDownloader/1.0 (educational project) Python/3.x'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
            
        img = Image.open(BytesIO(response.content))
        
        # Resize if necessary (maintaining aspect ratio)
        max_size = (800, 800)
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Save processed image
        img.save(filepath, "JPEG", quality=85)
        logger.info(f"Image saved successfully!")
        
        return filepath
    
    except Exception as e:
        logger.error(f"Error processing image: {e}")
        return None

def update_event_images():
    """Download images for all events."""
    try:
        client, events_collection = connect_to_mongodb()
        events = events_collection.find({})
        
        for event in events:
            event_name = event["name"]
            category = event.get("category", "")
            logger.info(f"\nProcessing: {event_name} ({category})")
            
            # Check if image needs to be downloaded
            image_path = event.get("image_url", "").lstrip("/")
            image_full_path = os.path.join(IMAGE_SAVE_PATH, image_path)
            
            if image_path and not os.path.exists(image_full_path):
                logger.info(f"Searching for image for {event_name}...")
                
                # Determine if this is a religious event
                is_religious_event = any(term in category.lower() for term in 
                    ['religion', 'faith', 'holy', 'sacred', 'spiritual', 'bahá\'í'])
                
                # Generate search variations
                search_variations = generate_search_variations(event_name, category)
                
                image_url = None
                source_used = None
                
                # Try each variation with both Wikimedia and Google
                for search_term in search_variations:
                    logger.info(f"Trying variation: {search_term}")
                    
                    # Try Wikimedia first
                    image_url = search_wikimedia_commons(search_term, is_religious_event)
                    if image_url:
                        source_used = f"Wikimedia Commons ({search_term})"
                        break
                    
                    # Then try Google
                    image_url = search_google_images(search_term, is_religious_event)
                    if image_url:
                        source_used = f"Google Images ({search_term})"
                        break
                    
                    # Add delay between attempts
                    time.sleep(2)
                
                if image_url:
                    logger.info(f"Found image URL from {source_used}: {image_url}")
                    filepath = download_and_process_image(image_url, image_path)
                    
                    if filepath:
                        events_collection.update_one(
                            {"_id": event["_id"]},
                            {
                                "$set": {
                                    "image_source": image_url,
                                    "image_source_platform": source_used,
                                    "last_updated": datetime.now(pytz.utc),
                                    "image_download_success": True
                                }
                            }
                        )
                        logger.info(f"Successfully updated database for {event_name}")
                else:
                    logger.warning(f"No suitable image found for {event_name} from any source")
                    # Update database to record the failed attempt
                    events_collection.update_one(
                        {"_id": event["_id"]},
                        {
                            "$set": {
                                "last_image_search_attempt": datetime.now(pytz.utc),
                                "image_download_success": False
                            }
                        }
                    )
            
            # Add delay between events
            time.sleep(2)
    
    except Exception as e:
        logger.error(f"Error processing events: {e}")
        raise
    finally:
        if 'client' in locals():
            client.close()
            logger.info("Database connection closed")

def main():
    """Main execution function."""
    try:
        logger.info("Starting image download process...")
        
        # Create required directories
        os.makedirs(IMAGE_SAVE_PATH, exist_ok=True)
        
        # Set up logging file
        log_file = os.path.join(os.path.dirname(IMAGE_SAVE_PATH), 'image_download.log')
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)
        
        # Start the download process
        update_event_images()
        
        logger.info("Image download process completed successfully!")
        
    except Exception as e:
        logger.error(f"Fatal error during image download: {e}")
        raise
        
    finally:
        # Clean up any remaining handlers
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

if __name__ == "__main__":
    main()