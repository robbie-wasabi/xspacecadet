import os
from openai import OpenAI
import logging
from datetime import datetime


class Chatbot:
    def __init__(self, api_key=None):
        self.client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))

    def chat(self, messages, model="gpt-4o"):
        try:
            response = self.client.chat.completions.create(model=model, messages=messages)
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"Failed to get chat response: {str(e)}")
            return None

    def generate_summary(self, transcript, prompt):
        messages = [
            {
                "role": "system",
                "content": "Summarize the conversation comprehensively and in detail. Begin with a 'Key Points' section at the top, presenting the main ideas as a concise bulleted list. Then, provide a thorough summary that captures all significant details, insights, and nuances from the conversation. Ensure to attribute statements and ideas to their respective speakers. Organize the summary in a logical flow, possibly by topics or chronologically. Include any notable quotes, disagreements, or consensus reached. If applicable, mention any action items, decisions made, or questions left unanswered. Conclude with a brief section on potential implications or next steps discussed.",
            },
            {"role": "user", "content": f"Here's a transcript: {transcript}\n\n{prompt}"},
        ]
        return self.chat(messages)
