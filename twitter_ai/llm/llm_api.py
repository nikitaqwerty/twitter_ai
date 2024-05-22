import os
from groq import Groq
from openai import OpenAI
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


if __name__ == "__main__":
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.config import Config

    logging.basicConfig(level=logging.INFO)
    API_PROVIDER = "openai"
    # Select API based on configuration
    if API_PROVIDER.lower() == "groq":
        api_handler = GroqAPIHandler(api_key=Config.GROQ_API_KEY)
    elif API_PROVIDER.lower() == "openai":
        api_handler = OpenAIAPIHandler(api_key=Config.OPENAI_API_KEY)
    else:
        raise ValueError("Unsupported API provider specified.")

    query = "Explain the importance of fast language models"
    response = api_handler.get_response(query)
    if response:
        print(response)
    else:
        print("Failed to get a response.")
