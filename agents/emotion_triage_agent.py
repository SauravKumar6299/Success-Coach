import os
import datetime
from dotenv import load_dotenv
from transformers import pipeline
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.tools import tool

from tools.add_to_signal import add_to_signal
from tools.add_to_calender import add_to_calendar

load_dotenv()

# Load the emotion model once in this module
try:
    emotion_classifier = pipeline("text-classification", model="SamLowe/roberta-base-go_emotions", top_k=None)
except Exception as e:
    print(f"Failed to load emotion model: {e}")
    emotion_classifier = None

llm = ChatOpenAI(model="gpt-5.4-mini-2026-03-17", temperature=0)

@tool
def analyze_student_emotions(message: str) -> str:
    """Analyzes text for urgent emotional triggers (anger, fear, grief, etc.)."""
    if not emotion_classifier:
        return "Emotion classifier unavailable."
    
    # Get the results and sort them by score descending
    results = emotion_classifier(message)[0]
    sorted_emotions = sorted(results, key=lambda x: x['score'], reverse=True)
    
    # Take the top 3 emotions
    top_7 = sorted_emotions[:7]
    
    urgent_emotions = {
        'hopelessness', 'anger', 'fear', 'grief', 'nervousness', 
        'sadness', 'remorse', 'disappointment', 'embarrassment', 'despair'
    }
    
    # Check if any of the top 3 are in the urgent list
    found_triggers = [e['label'] for e in top_7 if e['label'] in urgent_emotions]
    
    if found_triggers:
        return f"URGENT EMOTIONS DETECTED: {', '.join(found_triggers)}"
    
    # Fallback: Check if the highest score emotion is "neutral" or "approval" 
    # If the top emotion is truly benign, we are safe.
    return "No urgent emotions detected."

@tool
def escalate_to_human_coach(roll_no: str, signal_type: str, severity: str, urgency: str, reason: str, start_day_offset: int = 0) -> str:
    """
    Escalates a student's case to a human coach. 
    start_day_offset: 0 = Try scheduling for today. 1 = Force schedule for tomorrow.
    """
    ai_extracted_data = {
        "signal_type": signal_type,
        "severity": severity,
        "urgency": urgency,
        "reason": reason,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # 1. Add to Calendar FIRST to calculate the dynamic schedule
    cal_success, schedule_updates_or_msg = add_to_calendar(roll_no, ai_extracted_data, start_day_offset)
    
    if not cal_success:
        return f"Failed to escalate. Calendar Error: {schedule_updates_or_msg}"
        
    # 2. Add to Signal DB (Passing the calculated times to sync the sheets)
    sig_success, sig_msg = add_to_signal(roll_no, ai_extracted_data, schedule_updates_or_msg)
    
    return f"Escalation Results -> {sig_msg} | Calendar completely synchronized."


triage_tools = [analyze_student_emotions, escalate_to_human_coach]

triage_prompt = ChatPromptTemplate.from_messages([
    ("system", (
        "You are a Triage and Escalation Agent. "
        "Step 1: Use 'analyze_student_emotions' on the provided conversation summary. "
        "Step 2: If urgent emotions are detected, determine the context, create a concise 1-sentence reason, "
        "and immediately use 'escalate_to_human_coach' to alert the team. "
        "If no urgent emotions are found, output 'Student appears stable. No action required.'"
    )),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

triage_agent = create_openai_tools_agent(llm, triage_tools, triage_prompt)
emotion_triage_agent_executor = AgentExecutor(agent=triage_agent, tools=triage_tools, verbose=True)