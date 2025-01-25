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
from itertools import groupby

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
        load_dotenv()
        self.mongo_client = MongoClient(os.getenv('MONGODB_URI', 'mongodb://localhost:27017/'))
        self.db = self.mongo_client.events_db
        self.events_collection = self.db.events
        self.gmail_address = os.getenv('GMAIL_ADDRESS')
        self.gmail_app_password = os.getenv('GMAIL_APP_PASSWORD')
        
        if not all([self.gmail_address, self.gmail_app_password]):
            raise ValueError("Gmail credentials not found in environment variables")
        
        logging.info("Monthly Event Mailer initialized successfully")

    def get_current_month_events(self) -> List[Dict]:
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
        try:
            return date_obj.strftime('%B %d')
        except (ValueError, AttributeError):
            return 'Date TBD'

    def generate_html_template(self, events: List[Dict], current_date: datetime) -> str:
        month_year = current_date.strftime('%B %Y')
        
        all_events = events

        # Group events by category
        def group_events_by_category(events_list):
            # Define category order
            category_order = [
                'Religious Observances',
                'Cultural Observances', 
                'National Days',
                'International Days',
                'Month Long Observances'
            ]
            
            # Create category order lookup 
            category_order = [
                'Religious Observances',
                'Cultural Observances', 
                'National Days',
                'International Days',
                'Month Long Observances'
            ]
            
            # Sort events and group them
            grouped_events = {}
            for event in events_list:
                category = event.get('category', '')
                if category not in grouped_events:
                    grouped_events[category] = []
                grouped_events[category].append(event)
            
            # Create ordered dictionary based on defined order
            ordered_events = {}
            for category in category_order:
                if category in grouped_events:
                    ordered_events[category] = sorted(grouped_events[category], key=lambda x: x.get('start_date'))
                    
            # Add any remaining categories not in the predefined order
            for category, events in grouped_events.items():
                if category not in category_order and category:
                    ordered_events[category] = sorted(events, key=lambda x: x.get('start_date'))
            
            # Add any remaining categories at the end
            for category, events in grouped_events.items():
                if category not in category_order:
                    ordered_events[category] = events
                    
            return ordered_events

        def create_event_blocks(events_list):
            rows_html = ''
            current_row = []
            
            for event in events_list:
                start_date = event['start_date']
                end_date = event['end_date']
                
                if start_date == end_date:
                    date_display = self.format_date(start_date)
                else:
                    date_display = f"{self.format_date(start_date)} - {self.format_date(end_date)}"
                
                event_html = f'''
                    <td style="width: 25%; padding: 6px; vertical-align: top;">
                        <a href="https://dedi.eecs.yorku.ca/#/event/{event['_id']}" 
                           style="text-decoration: none; color: white; display: block;">
                            <div style="background-color: #4299e1; border-radius: 6px; min-height: 120px; 
                                      box-sizing: border-box;">
                                <table cellpadding="0" cellspacing="0" style="width: 100%; height: 120px;">
                                    <tr>
                                        <td style="padding: 16px 16px 6px 16px; vertical-align: top;">
                                            <div style="font-size: 16px; font-weight: 500; line-height: 1.3;">
                                                {event['name']}
                                            </div>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 0 16px 16px 16px; vertical-align: bottom; height: 1px;">
                                            <div style="font-size: 14px;">
                                                {date_display}
                                            </div>
                                        </td>
                                    </tr>
                                </table>
                            </div>
                        </a>
                    </td>
                '''
                current_row.append(event_html)
                
                if len(current_row) == 4:
                    rows_html += f"<tr>{''.join(current_row)}</tr>"
                    current_row = []
            
            if current_row:
                while len(current_row) < 4:
                    current_row.append('<td style="width: 25%; padding: 6px;"></td>')
                rows_html += f"<tr>{''.join(current_row)}</tr>"
            
            return rows_html

        template = f'''
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Monthly Events Digest - {month_year}</title>
            </head>
            <body style="max-width: 1200px; margin: 0 auto; padding: 32px 24px;
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 
                        Roboto, Helvetica, Arial, sans-serif; background-color: #f7fafc;">
                
                <div style="text-align: center; margin-bottom: 40px;">
                    <h1 style="margin: 0; color: #2d3748; font-size: 36px; font-weight: 700;">
                        EDI Project Events Email
                    </h1>
                </div>
        '''
        
        template += '''
                <div style="text-align: left; margin-bottom: 24px;">
                    <h2 style="margin: 0; color: #2d3748; font-size: 32px; font-weight: 700;">
                        Observances
                    </h2>
                </div>
            '''
            
        grouped_events = group_events_by_category(all_events)
        for category, events in grouped_events.items():
            template += f'''
                <div style="margin-bottom: 32px;">
                    <h3 style="color: #4a5568; font-size: 24px; margin: 16px 0;">
                        {category}
                    </h3>
                    <table style="width: 100%; border-collapse: separate; border-spacing: 0;">
                        {create_event_blocks(events)}
                    </table>
                </div>
            '''
        
        template += '''
                <div style="text-align: center; color: #718096; font-size: 13px; 
                           margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0;">
                    York University Equity, Diversity and Inclusion Calendar Project
                </div>
            </body>
            </html>
        '''
        
        return template

    def send_monthly_digest(self, recipients: List[str]) -> None:
        try:
            current_date = datetime.now(pytz.UTC)
            events = self.get_current_month_events()
            
            if not events:
                logging.info(f"No events found for {current_date.strftime('%B %Y')}")
                return
            
            msg = MIMEMultipart()
            msg['Subject'] = f'Monthly Events - {current_date.strftime("%B %Y")}'
            msg['From'] = self.gmail_address
            msg['To'] = ', '.join(recipients)
            
            html_content = self.generate_html_template(events, current_date)
            msg.attach(MIMEText(html_content, 'html'))
            
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
        recipients = ["arnav44malhotra@gmail.com"]
        mailer = MonthlyEventMailer()
        mailer.send_monthly_digest(recipients)
        logging.info("Monthly digest process completed successfully")
        
    except Exception as e:
        logging.error(f"Fatal error in monthly digest: {str(e)}")
        raise
