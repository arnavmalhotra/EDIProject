import os

from datetime import datetime, timedelta

import calendar

from pymongo import MongoClient

from email.mime.text import MIMEText

from email.mime.multipart import MIMEMultipart

import smtplib

from dotenv import load_dotenv

import pytz

from typing import List, Dict

import logging



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

        

        # Separate regular and extended events

        regular_events = {}

        extended_events = []

        

        for event in events:

            duration = (event['end_date'] - event['start_date']).days

            if duration > 6:

                extended_events.append(event)

            else:

                regular_events[event['start_date'].day] = event

                

        return regular_events, extended_events



    def generate_calendar_template(self, regular_events: Dict, extended_events: List[Dict], current_date: datetime) -> str:

        month_year = current_date.strftime('%B %Y')

        

        template = f'''

        <!DOCTYPE html>

        <html>

        <head>

            <meta charset="utf-8">

            <meta name="viewport" content="width=device-width, initial-scale=1.0">

            <title>EDI Calendar - {month_year}</title>

            <style>

                .calendar-cell {{ vertical-align: top; height: 100px; }}

                .event-link {{ text-decoration: none; color: inherit; }}

                .event-cell {{ background-color: #bce3e7; }}

                .extended-event {{ 

                    background-color: #bce3e7;

                    padding: 10px;

                    margin: 5px 0;

                    border-radius: 4px;

                }}

            </style>

        </head>

        <body style="max-width: 1000px; margin: 0 auto; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;">

            <h1 style="text-align: center; color: #2d3748; margin-bottom: 30px;">Month: {month_year}</h1>

            

            <table style="width: 100%; border-collapse: separate; border-spacing: 2px;">

                <tr style="background-color: #75C7C3;">

                    <th style="width: 14.28%; padding: 10px; color: white;">Sun</th>

                    <th style="width: 14.28%; padding: 10px; color: white;">Mon</th>

                    <th style="width: 14.28%; padding: 10px; color: white;">Tues</th>

                    <th style="width: 14.28%; padding: 10px; color: white;">Weds</th>

                    <th style="width: 14.28%; padding: 10px; color: white;">Thurs</th>

                    <th style="width: 14.28%; padding: 10px; color: white;">Fri</th>

                    <th style="width: 14.28%; padding: 10px; color: white;">Sat</th>

                </tr>

        '''

        

        # Calculate first day offset (0 = Monday, 6 = Sunday)

        first_day = datetime(current_date.year, current_date.month, 1)

        first_weekday = first_day.weekday()

        # Adjust for Sunday start (shift by 6)

        first_weekday = (first_weekday + 1) % 7

        

        # Get number of days in month

        _, num_days = calendar.monthrange(current_date.year, current_date.month)

        

        day = 1

        template += '<tr>'

        

        # Add empty cells for days before the 1st

        for _ in range(first_weekday):

            template += '<td style="background-color: #f0f0f0; border: 1px solid #e2e8f0;"></td>'

        

        # Fill in the days

        current_col = first_weekday

        while day <= num_days:

            if current_col == 7:

                template += '</tr><tr>'

                current_col = 0

            

            event = regular_events.get(day)

            if event:

                template += f'''

                    <td class="calendar-cell event-cell" style="border: 1px solid #e2e8f0; padding: 8px;">

                        <div style="font-weight: bold;">{day}</div>

                        <a href="https://dedi.eecs.yorku.ca/#/event/{event['_id']}" class="event-link">

                            <div style="font-size: 12px; margin-top: 4px;">{event['name']}</div>

                        </a>

                    </td>

                '''

            else:

                template += f'''

                    <td class="calendar-cell" style="background-color: #f0f0f0; border: 1px solid #e2e8f0; padding: 8px;">

                        <div>{day}</div>

                    </td>

                '''

            

            day += 1

            current_col += 1

        

        # Fill in remaining cells

        while current_col < 7:

            template += '<td style="background-color: #f7fafc; border: 1px solid #e2e8f0;"></td>'

            current_col += 1

        

        template += '</tr></table>'

        

        # Add extended observances section

        if extended_events:

            template += '''

                <div style="margin-top: 40px;">

                    <h2 style="color: #2d3748;">Extended Observances</h2>

            '''

            

            for event in extended_events:

                start_date = event['start_date'].strftime('%B %d')

                end_date = event['end_date'].strftime('%B %d')

                template += f'''

                    <a href="https://dedi.eecs.yorku.ca/#/event/{event['_id']}" style="text-decoration: none; color: inherit;">

                        <div class="extended-event">

                            <div style="font-weight: bold;">{event['name']}</div>

                            <div style="font-size: 14px;">{start_date} - {end_date}</div>

                        </div>

                    </a>

                '''

            

            template += '</div>'

        

        template += '''

            <div style="text-align: center; margin-top: 20px; color: #718096; font-size: 13px;">

                York University Equity, Diversity and Inclusion Calendar Project

            </div>

        </body>

        </html>

        '''

        

        return template



    def send_monthly_digest(self, recipients: List[str]) -> None:

        try:

            current_date = datetime.now(pytz.UTC)

            regular_events, extended_events = self.get_current_month_events()

            

            if not regular_events and not extended_events:

                logging.info(f"No events found for {current_date.strftime('%B %Y')}")

                return

            

            msg = MIMEMultipart()

            msg['Subject'] = f'EDI Calendar - {current_date.strftime("%B %Y")}'

            msg['From'] = self.gmail_address

            msg['To'] = ', '.join(recipients)

            

            html_content = self.generate_calendar_template(regular_events, extended_events, current_date)

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
