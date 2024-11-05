import discord
import os
import json
import datetime
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)

# Load environment variables from .env file
load_dotenv()

# Initialize Discord client with specific intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
client = discord.Client(intents=intents)

# Load questions from JSON file
with open('questions.json', 'r') as f:
    questions_data = json.load(f)

# Directory where journal entries will be saved
DATA_DIR = 'journal_entries'

# Ensure the directory exists
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def check_incomplete_entry(entry):
    # Check if any question response is None
    incomplete = any(e['response'] is None for e in entry['entries'])
    
    # Check if any habit responses are None
    for e in entry['entries']:
        if e.get('response') and isinstance(e['response'], dict):  # Check if it's a habits response
            if any(v is None for v in e['response'].values()):
                incomplete = True
                break
    
    return incomplete

async def send_daily_questions():
    logger.info("Starting daily questions routine...")
    
    for guild in client.guilds:
        logger.info(f"Processing guild: {guild.name}")
        
        # Find the 'echoes' channel
        echoes_channel = discord.utils.get(guild.channels, name="echoes")
        
        if echoes_channel is None:
            logger.error(f"Could not find 'echoes' channel in guild {guild.name}")
            continue
            
        logger.info(f"Found 'echoes' channel: {echoes_channel.name}")

        # # Send starting message
        # await echoes_channel.send(f"*TIME FOR JOURNAL ENTRY!*")

        for member in guild.members:
            if member.bot:
                continue
                
            logger.info(f"Processing member: {member.name}#{member.discriminator}")

            user_id = member.id
            today = str(datetime.date.today())

            entry = {
                "_id": user_id,
                'date': today,
                'entries': [],
                'Partial/Incomplete': 'no'  # Will be updated at the end
            }
            
            await echoes_channel.send(f"Hey {member.mention}! It's time to fill out you daily journal. Let's get started!")

            try:
                for question in questions_data['questions']:
                    # Send question without mentioning the user
                    await echoes_channel.send(f"{question['text']}")
                    
                    if question['type'] == 'text' or question['type'] == 'rating':
                        response = await client.wait_for(
                            'message',
                            check=lambda m: m.author == member and m.channel == echoes_channel,
                            timeout=None
                        )
                        
                        entry['entries'].append({
                            'question_id': question['id'],
                            'question': question['text'],
                            'response': response.content
                        })

                    elif question['type'] == 'habit':
                        habits_responses = {}
                        
                        # Send habits message
                        # habit_msg = await echoes_channel.send("Did you complete these habits today?")
                        
                        for habit in question['habits']:
                            # Send each habit as a separate message
                            habit_question = await echoes_channel.send(f"{habit['name']}")
                            await habit_question.add_reaction("✅")
                            await habit_question.add_reaction("❌")
                            
                            try:
                                reaction, _ = await client.wait_for(
                                    'reaction_add',
                                    check=lambda r, u: u == member and str(r.emoji) in ["✅", "❌"] and r.message.id == habit_question.id,
                                    timeout=None
                                )
                                
                                habits_responses[habit["name"]] = 'yes' if str(reaction.emoji) == '✅' else 'no'
                            except Exception as e:
                                logger.error(f"Error processing habit reaction: {str(e)}")
                                habits_responses[habit["name"]] = None
                        
                        entry["entries"].append({
                            'question_id': question["id"],
                            'question': question["text"],
                            'response': habits_responses
                        })

            except Exception as e:
                logger.error(f"Error processing questions for {member.name}: {str(e)}")
                continue

            # Check if entry is incomplete and update status
            entry['Partial/Incomplete'] = 'yes' if check_incomplete_entry(entry) else 'no'

            # Save the entry
            try:
                filename = f"{DATA_DIR}/{user_id}_{today}.json"
                with open(filename, 'w') as f:
                    json.dump(entry, f, indent=4)
                logger.info(f"Saved entry for {Amember.name}")
            except Exception as e:
                logger.error(f"Error saving entry for {member.name}: {str(e)}")

            await echoes_channel.send("All done! Your daily jourAnal has been saved.")

@client.event
async def on_ready():
    logger.info(f'Logged in as {client.user}')
    
    try:
        # Set up scheduler
        scheduler = AsyncIOScheduler()
        ist_timezone = timezone('Asia/Kolkata')
        
        # Get current time
        now = datetime.datetime.now(ist_timezone)
        
        # Calculate next minute
        next_minute = (now + datetime.timedelta(minutes=1)).minute
        
        # Schedule job for next minute
        scheduler.add_job(
            send_daily_questions,
            CronTrigger(
                hour=now.hour,
                minute=next_minute,
                timezone=ist_timezone
            )
        )
        
        scheduler.start()
        logger.info("Scheduler started successfully")
        
        # Log next run time
        next_run = scheduler.get_jobs()[0].next_run_time
        logger.info(f"Next scheduled run: {next_run}")
        
    except Exception as e:
        logger.error(f"Error setting up scheduler: {str(e)}")

@client.event
async def on_error(event, *args, **kwargs):
    logger.error(f"Error in {event}: {str(args[0])}")

# Run the bot
try:
    TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    if not TOKEN:
        raise ValueError("No token found in environment variables")
    
    client.run(TOKEN)
except Exception as e:
    logger.error(f"Error running bot: {str(e)}")