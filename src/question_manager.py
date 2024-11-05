import json
import os
from datetime import datetime
import logging

# Setup paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIMESTAMPS_FILE = os.path.join(BASE_DIR, 'other/question_timestamps.json')
QUESTIONS_FILE = os.path.join(BASE_DIR, 'src', 'questions.json')

# Setup logging
logger = logging.getLogger('discord')

def validate_question(question):
    """Validate that a question has all required fields."""
    required_fields = ['id', 'text', 'type']
    valid = all(field in question for field in required_fields)
    if not valid:
        logger.warning(f"Invalid question format: {question}")
    return valid

def load_timestamps():
    """Load or create timestamps file."""
    try:
        with open(TIMESTAMPS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        timestamps = {
            "last_asked": {
                "weekly": {},
                "biweekly": {},
                "twicemonthly": {},
                "monthly": {}
            }
        }
        save_timestamps(timestamps)
        return timestamps

def save_timestamps(timestamps):
    """Save timestamps to file."""
    try:
        with open(TIMESTAMPS_FILE, 'w') as f:
            json.dump(timestamps, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving timestamps: {str(e)}")

def should_ask_question(question_id, frequency):
    """Determine if a question should be asked based on its frequency."""
    if frequency == 'daily':
        return True
        
    timestamps = load_timestamps()
    
    if frequency not in timestamps['last_asked']:
        timestamps['last_asked'][frequency] = {}
    
    last_asked = timestamps['last_asked'][frequency].get(str(question_id))
    
    # If never asked before
    if last_asked is None:
        return True
    
    # Check if enough time has passed
    last_asked_date = datetime.fromisoformat(last_asked)
    current_date = datetime.now()
    
    intervals = {
        "weekly": 7,
        "biweekly": 14,
        "twicemonthly": 15,
        "monthly": 30
    }
    
    return (current_date - last_asked_date).days >= intervals.get(frequency, 0)

def update_question_timestamp(question_id, frequency):
    """Update the last asked timestamp for a question."""
    if frequency == 'daily':
        return
        
    timestamps = load_timestamps()
    timestamps['last_asked'][frequency][str(question_id)] = datetime.now().isoformat()
    save_timestamps(timestamps)

def get_questions_for_today():
    """Get the list of questions that should be asked today."""
    try:
        with open(QUESTIONS_FILE, 'r') as f:
            questions_data = json.load(f)
    except FileNotFoundError:
        logger.error(f"Questions file not found at {QUESTIONS_FILE}")
        return []
    except json.JSONDecodeError:
        logger.error("Invalid JSON in questions file")
        return []
    
    questions_for_today = []
    
    for question in questions_data.get('questions', []):
        if not validate_question(question):
            continue
            
        frequency = question.get('frequency', 'daily')
        if frequency == 'daily' or should_ask_question(question['id'], frequency):
            questions_for_today.append(question)
    
    return questions_for_today