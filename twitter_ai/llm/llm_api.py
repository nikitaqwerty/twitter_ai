import os
from groq import Groq
from openai import OpenAI
from g4f.client import Client
import logging


class APIHandler:
    def __init__(self, api_key, model=None):
        self.api_key = api_key
        self.model = model  # Store the model name as an instance variable

    def get_response(self, query):
        raise NotImplementedError("This method should be overridden by subclasses.")


class GroqAPIHandler(APIHandler):
    DEFAULT_MODEL = "llama3-70b-8192"

    def __init__(self, api_key, model=None):
        if model is None:
            model = self.DEFAULT_MODEL
        super().__init__(api_key, model)
        self.client = Groq(api_key=api_key)

    def get_response(self, query):
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[{"role": "user", "content": query}], model=self.model
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            logging.error(f"GroqAPI error: {e}")
            return None


class OpenAIAPIHandler(APIHandler):
    DEFAULT_MODEL = "gpt-3.5-turbo"

    def __init__(self, api_key, model=None):
        if model is None:
            model = self.DEFAULT_MODEL
        super().__init__(api_key, model)
        self.client = OpenAI(api_key=self.api_key)

    def get_response(self, query):
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": query},
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"OpenAI API error: {e}")
            return None


class g4fAPIHandler(APIHandler):
    DEFAULT_MODEL = "gpt-4o"

    def __init__(self, api_key="", model=None):
        if model is None:
            model = self.DEFAULT_MODEL
        super().__init__(api_key, model)
        self.client = Client()

    def get_response(self, query):
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": query},
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"G4F API error: {e}")
            return None


if __name__ == "__main__":
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.config import Config

    logging.basicConfig(level=logging.INFO)
    API_PROVIDER = "g4f"
    # Select API based on configuration
    if API_PROVIDER.lower() == "groq":
        api_handler = GroqAPIHandler(api_key=Config.GROQ_API_KEY)
    elif API_PROVIDER.lower() == "openai":
        api_handler = OpenAIAPIHandler(api_key=Config.OPENAI_API_KEY)
    elif API_PROVIDER.lower() == "g4f":
        api_handler = g4fAPIHandler()
    else:
        raise ValueError("Unsupported API provider specified.")

    query = "What model am I talking with?"
    response = api_handler.get_response(query)
    if response:
        print(response)
    else:
        print("Failed to get a response.")
