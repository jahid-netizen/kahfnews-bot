import os
import logging
import asyncio
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
from telegram import Bot
from telegram.constants import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from openai import OpenAI

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "8944689234:AAGKlgwOdYvxOfx5XQONLgqy3r9zszTPJ_g")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@kahfnews")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASE)

# Websites to scrape
URLS = ["https://kahf.com.tr/", "https://kahfguard.com/"]

def scrape_content():
    """Scrapes content from the target websites."""
    combined_text = ""
    for url in URLS:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            # Extract text from paragraphs and headings
            text = " ".join([t.get_text() for t in soup.find_all(['p', 'h1', 'h2', 'h3'])])
            combined_text += f"\nSource: {url}\nContent: {text[:2000]}\n" # Limit text per site
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
    return combined_text

async def generate_content(scraped_data, language):
    """Generates social media content using OpenAI."""
    prompt = f"""
    Based on the following information about Kahf (a digital safety and Islamic values oriented tech company):
    {scraped_data}
    
    Create a professional and engaging social media post for Telegram.
    The post should be in {language}.
    Include relevant hashtags and a call to action.
    Format the output as a Telegram post with emojis.
    Type: Social media post or short article.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a social media manager for Kahf, a company focused on safe internet and Islamic values."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error generating content: {e}")
        return None

async def post_to_telegram(content):
    """Posts the generated content to the Telegram channel."""
    if not content:
        return
    
    bot = Bot(token=BOT_TOKEN)
    try:
        await bot.send_message(chat_id=CHANNEL_ID, text=content, parse_mode=ParseMode.MARKDOWN)
        logger.info("Successfully posted to Telegram.")
    except Exception as e:
        logger.error(f"Error posting to Telegram: {e}")

# Track the last language used to alternate
last_language = "English"

async def scheduled_job():
    """The main job that runs at scheduled times."""
    global last_language
    
    # Alternate language
    current_language = "Bengali" if last_language == "English" else "English"
    last_language = current_language
    
    logger.info(f"Starting scheduled job for {current_language} content...")
    
    scraped_data = scrape_content()
    if not scraped_data:
        logger.warning("No data scraped. Skipping job.")
        return
        
    content = await generate_content(scraped_data, current_language)
    if content:
        await post_to_telegram(content)
    else:
        logger.warning("Failed to generate content.")

async def main():
    # Initialize scheduler
    scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Dhaka'))
    
    # Schedule at 9:00 AM BDT
    scheduler.add_job(scheduled_job, 'cron', hour=9, minute=0)
    
    # Schedule at 7:00 PM BDT
    scheduler.add_job(scheduled_job, 'cron', hour=19, minute=0)
    
    scheduler.start()
    logger.info("Scheduler started. Bot is running...")
    
    # Keep the script running
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
