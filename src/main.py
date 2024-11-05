import discord
import os
import json
import datetime
import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone
from dotenv import load_dotenv
import sys 

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from question_manager import get_questions_for_today, update_question_timestamp

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='a')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# Load environment variables
load_dotenv()

# Initialize Discord client
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
client = discord.Client(intents=intents)

# Set up data directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'journal_entries')
QUESTIONS_FILE = os.path.join(BASE_DIR, 'src', 'questions.json')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

if not os.path.exists(QUESTIONS_FILE):
    logger.error(f"Questions file not found at {QUESTIONS_FILE}")
    raise FileNotFoundError(f"Questions file not found at {QUESTIONS_FILE}")

def check_incomplete_entry(entry):
    """Check if any responses in the entry are incomplete."""
    # Check text/rating responses
    incomplete = any(e['response'] is None for e in entry['entries'])
    
    # Check habit responses
    for e in entry['entries']:
        if e.get('response') and isinstance(e['response'], dict):
            if any(v is None for v in e['response'].values()):
                incomplete = True
                break
    
    return incomplete

async def handle_text_question(question, member, echoes_channel, entry):
    """Handle text or rating type questions."""
    try:
        response = await client.wait_for(
            'message',
            check=lambda m: m.author == member and m.channel == echoes_channel,
            timeout=300  # 5 minutes timeout
        )
        
        entry['entries'].append({
            'question_id': question['id'],
            'question': question['text'],
            'response': response.content,
            'frequency': question.get('frequency', 'daily')
        })
        return True
    except asyncio.TimeoutError:
        await echoes_channel.send("No response received within 5 minutes. Moving to next question.")
        entry['entries'].append({
            'question_id': question['id'],
            'question': question['text'],
            'response': None,
            'frequency': question.get('frequency', 'daily')
        })
        return False

async def handle_habit_question(question, member, echoes_channel, entry):
    """Handle habit type questions."""
    habits_responses = {}
    
    for habit in question['habits']:
        try:
            habit_question = await echoes_channel.send(f"{habit['name']}")
            await habit_question.add_reaction("✅")
            await habit_question.add_reaction("❌")
            
            reaction, _ = await client.wait_for(
                'reaction_add',
                check=lambda r, u: u == member and str(r.emoji) in ["✅", "❌"] and r.message.id == habit_question.id,
                timeout=300
            )
            
            habits_responses[habit["name"]] = 'yes' if str(reaction.emoji) == '✅' else 'no'
        except asyncio.TimeoutError:
            await echoes_channel.send(f"No response received for habit: {habit['name']}")
            habits_responses[habit["name"]] = None
        except Exception as e:
            logger.error(f"Error processing habit reaction: {str(e)}")
            habits_responses[habit["name"]] = None
    
    entry["entries"].append({
        'question_id': question["id"],
        'question': question["text"],
        'response': habits_responses,
        'frequency': question.get('frequency', 'daily')
    })
    return True

async def send_daily_questions():
    """Main function to send daily questions and collect responses."""
    logger.info("Starting daily questions routine...")
    
    todays_questions = get_questions_for_today()
    if not todays_questions:
        logger.error("No questions found for today")
        return
    
    for guild in client.guilds:
        logger.info(f"Processing guild: {guild.name}")
        
        echoes_channel = discord.utils.get(guild.channels, name="echoes")
        if echoes_channel is None:
            logger.error(f"Could not find 'echoes' channel in guild {guild.name}")
            continue
            
        for member in guild.members:
            if member.bot:
                continue
                
            logger.info(f"Processing member: {member.name}#{member.discriminator}")
            
            entry = {
                "_id": member.id,
                'date': str(datetime.date.today()),
                'entries': [],
                'Partial/Incomplete': 'no'
            }
            
            await echoes_channel.send(f"Hey {member.mention}! It's time for your daily journal.")
            
            try:
                for question in todays_questions:
                    await echoes_channel.send(f"{question['text']}")
                    
                    success = False
                    if question['type'] in ['text', 'rating']:
                        success = await handle_text_question(question, member, echoes_channel, entry)
                    elif question['type'] == 'habit':
                        success = await handle_habit_question(question, member, echoes_channel, entry)
                    
                    # Update timestamp only if question was successfully answered
                    if success and question.get('frequency') != 'daily':
                        update_question_timestamp(question['id'], question['frequency'])
                
                # Save entry
                entry['Partial/Incomplete'] = 'yes' if check_incomplete_entry(entry) else 'no'
                filename = os.path.join(DATA_DIR, f"{member.id}_{entry['date']}.json")
                
                with open(filename, 'w') as f:
                    json.dump(entry, f, indent=4)
                logger.info(f"Saved entry for {member.name}")
                
                await echoes_channel.send("*Today's responses have been saved.*")
                
            except Exception as e:
                logger.error(f"Error processing questions for {member.name}: {str(e)}")
                await echoes_channel.send("An error occurred while processing your responses.")

@client.event
async def on_ready():
    """Set up scheduler when bot starts."""
    logger.info(f'Logged in as {client.user}')
    
    try:
        scheduler = AsyncIOScheduler()
        ist_timezone = timezone('Asia/Kolkata')
        
        # Schedule for 9 AM IST daily
        scheduler.add_job(
            send_daily_questions,
            CronTrigger(
                hour=15,
                minute=45,
                timezone=ist_timezone
            )
        )
        
        scheduler.start()
        logger.info("Scheduler started successfully")
        logger.info(f"Next run scheduled for: {scheduler.get_jobs()[0].next_run_time}")
        
    except Exception as e:
        logger.error(f"Error setting up scheduler: {str(e)}")

@client.event
async def on_error(event, *args, **kwargs):
    """Handle any errors that occur."""
    logger.error(f"Error in {event}: {str(args[0])}")

# Run the bot
if __name__ == "__main__":
    try:
        TOKEN = os.getenv('DISCORD_BOT_TOKEN')
        if not TOKEN:
            raise ValueError("No token found in environment variables")
        
        client.run(TOKEN)
    except Exception as e:
        logger.error(f"Error running bot: {str(e)}")