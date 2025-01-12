import os
from datetime import datetime
from pymongo import MongoClient
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from dotenv import load_dotenv
import pytz
from typing import List, Dict
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monthly_digest.log'),
        logging.StreamHandler()
    ]
)

class MonthlyEventMailer:
    def __init__(self):
        """Initialize EventMailer with MongoDB and Gmail configurations"""
        load_dotenv()
        
        # MongoDB setup
        self.mongo_client = MongoClient(os.getenv('MONGODB_URI', 'mongodb://localhost:27017/'))
        self.db = self.mongo_client.events_db
        self.events_collection = self.db.events
        
        # Gmail setup
        self.gmail_address = os.getenv('GMAIL_ADDRESS')
        self.gmail_app_password = os.getenv('GMAIL_APP_PASSWORD')
        
        if not all([self.gmail_address, self.gmail_app_password]):
            raise ValueError("Gmail credentials not found in environment variables")
        
        logging.info("Monthly Event Mailer initialized successfully")

    def get_current_month_events(self) -> List[Dict]:
        """Fetch events for the current month from MongoDB."""
        now = datetime.now(pytz.UTC)
        month_start = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=pytz.UTC)
        if now.month == 12:
            month_end = datetime(now.year + 1, 1, 1, 0, 0, 0, tzinfo=pytz.UTC)
        else:
            month_end = datetime(now.year, now.month + 1, 1, 0, 0, 0, tzinfo=pytz.UTC)

        logging.info(f"Fetching events between {month_start} and {month_end}")
        
        events = list(self.events_collection.find({
            "$or": [
                {"start_date": {"$gte": month_start, "$lt": month_end}},
                {"end_date": {"$gte": month_start, "$lt": month_end}},
                {
                    "start_date": {"$lt": month_end},
                    "end_date": {"$gte": month_start}
                }
            ]
        }).sort("start_date", 1))
        
        logging.info(f"Found {len(events)} events for {now.strftime('%B %Y')}")
        return events

    def format_date(self, date_obj: datetime) -> str:
        """Format datetime object to readable format."""
        try:
            return date_obj.strftime('%B %d, %Y')
        except (ValueError, AttributeError):
            return 'Date TBD'

    def generate_html_template(self, events: List[Dict], current_date: datetime) -> str:
        """Generate HTML email template with events."""
        month_year = current_date.strftime('%B %Y')
        
        events_html = ''
        for event in events:
            # Format dates
            start_date = self.format_date(event['start_date'])
            end_date = self.format_date(event['end_date'])
            date_display = start_date if start_date == end_date else f"{start_date} - {end_date}"
            
            events_html += f'''
                <div style="margin-bottom: 24px; background: white; border-radius: 12px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.05); padding: 20px;">
                    <div style="display: flex; justify-content: space-between; 
                            align-items: center; margin-bottom: 8px;">
                        <h2 style="margin: 0; font-size: 18px; color: #1a1a1a; 
                                font-weight: 600; line-height: 1.3; flex: 1;">
                            {event['name']}
                        </h2>
                        <div style="background: #f0f7ff; color: #0066cc;
                                padding: 4px 12px; border-radius: 6px;
                                font-size: 12px; font-weight: 500;
                                margin-left: 12px; white-space: nowrap;">
                            {event['category']}
                        </div>
                    </div>
                    
                    <div style="font-size: 13px; color: #666; margin-bottom: 10px;">
                        {date_display}
                    </div>
                    
                    <div style="font-size: 14px; line-height: 1.5; color: #444;">
                        {event.get('concise_details', '')}
                    </div>
                </div>
            '''

        return f'''
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
            </head>
            <body style="max-width: 680px; margin: 0 auto; padding: 24px;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 
                    Roboto, Helvetica, Arial, sans-serif; background-color: #f5f5f7;">
                
                <div style="text-align: center; margin-bottom: 32px;">
                    <h1 style="margin: 0; color: #1a1a1a; font-size: 28px; font-weight: 700;">
                        Cultural and Religious Events
                    </h1>
                    <div style="color: #666; font-size: 16px; margin-top: 8px;">
                        {month_year}
                    </div>
                </div>
                
                {events_html}
                
                <div style="text-align: center; color: #666; font-size: 12px; 
                        margin-top: 32px; padding-top: 16px; border-top: 1px solid #e5e5e5;">
                    Generated on {datetime.now(pytz.utc).strftime('%B %d, %Y')}
                </div>
            </body>
            </html>
        '''

    def send_monthly_digest(self, recipients: List[str]) -> None:
        """Send the monthly digest email."""
        try:
            current_date = datetime.now(pytz.UTC)
            events = self.get_current_month_events()
            
            if not events:
                logging.info(f"No events found for {current_date.strftime('%B %Y')}")
                return
            
            # Create email
            msg = MIMEMultipart()
            msg['Subject'] = f'Monthly Events - {current_date.strftime("%B %Y")}'
            msg['From'] = self.gmail_address
            msg['To'] = ', '.join(recipients)
            
            # Generate and attach HTML content
            html_content = self.generate_html_template(events, current_date)
            msg.attach(MIMEText(html_content, 'html'))
            
            # Send email
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(self.gmail_address, self.gmail_app_password)
                server.send_message(msg)
                logging.info(f"Monthly digest sent successfully for {current_date.strftime('%B %Y')}")
            
        except Exception as e:
            logging.error(f"Error sending monthly digest: {str(e)}")
            raise
        finally:
            self.mongo_client.close()

if __name__ == "__main__":
    try:
        recipients = ["ediprojectcalendarapplication@gmail.com"]
        mailer = MonthlyEventMailer()
        mailer.send_monthly_digest(recipients)
        logging.info("Monthly digest process completed successfully")
        
    except Exception as e:
        logging.error(f"Fatal error in monthly digest: {str(e)}")
        raise