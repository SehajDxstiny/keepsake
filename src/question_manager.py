import json
import os
from datetime import datetime, timedelta

def should_ask_question(question_id, frequency):
    # Use absolute path for the timestamps file
    timestamps_file = os.path.join(os.path.dirname(__file__), 'question_timestamps.json')
    
    # Load or create the timestamp file
    try:
        with open(timestamps_file, 'r') as f:
            timestamps = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Create default structure with all frequencies
        timestamps = {
            "last_asked": {
                "weekly": {},
                "biweekly": {},
                "twicemonthly": {},
                "monthly": {}
            }
        }
    
    # If frequency is daily, always return True
    if frequency == 'daily':
        return True
    
    # Ensure the frequency exists in the timestamps
    if frequency not in timestamps['last_asked']:
        timestamps['last_asked'][frequency] = {}
    
    last_asked = timestamps['last_asked'][frequency].get(str(question_id))
    
    # If never asked before, should ask and update timestamp
    if last_asked is None:
        timestamps['last_asked'][frequency][str(question_id)] = datetime.now().isoformat()
        with open(timestamps_file, 'w') as f:
            json.dump(timestamps, f, indent=2)
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
    
    should_ask = (current_date - last_asked_date).days >= intervals.get(frequency, 0)
    
    # Update timestamp only if we're going to ask the question
    if should_ask:
        timestamps['last_asked'][frequency][str(question_id)] = current_date.isoformat()
        with open(timestamps_file, 'w') as f:
            json.dump(timestamps, f, indent=2)
    
    return should_ask

def get_questions_for_today():
    # Use absolute path for the questions file
    questions_file = os.path.join(os.path.dirname(__file__), 'questions.json')
    
    with open(questions_file, 'r') as f:
        questions_data = json.load(f)
    
    questions_for_today = []
    
    for question in questions_data['questions']:
        frequency = question.get('frequency', 'daily')
        if frequency == 'daily' or should_ask_question(question['id'], frequency):
            questions_for_today.append(question)
    
    return questions_for_today