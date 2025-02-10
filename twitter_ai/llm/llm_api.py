import os
import base64
import logging
from groq import Groq
from openai import OpenAI
from g4f.client import Client as g4fClient
from g4f.Provider import OpenaiChat
from g4f.cookies import set_cookies_dir, read_cookie_files


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
            error_message = str(e)
            logging.error(f"GroqAPI error: {error_message}")
            if "context_length_exceeded" in error_message:
                return {"error": "context_length_exceeded"}
            if "rate_limit_exceeded" in error_message:
                return {"error": "rate_limit_exceeded"}
            return None

    def get_vlm_response(
        self, prompt, image_path, model="llama-3.2-90b-vision-preview"
    ):
        """
        Sends a VLM request with an image and a text prompt using the Groq client.
        Uses the VLM model: 'llama-3.2-90b-vision-preview'.
        """
        try:
            with open(image_path, "rb") as image_file:
                encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{encoded_image}",
                                },
                            },
                        ],
                    }
                ],
                model=model,
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            logging.error(f"Groq VLM API error: {e}")
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

    def __init__(self, api_key="", model=None, cookies_dir=""):
        if model is None:
            model = self.DEFAULT_MODEL
        super().__init__(api_key, model)
        if cookies_dir:
            set_cookies_dir(cookies_dir)
            read_cookie_files(cookies_dir)
        self.client = g4fClient(provider=OpenaiChat)

    def get_response(self, query):
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": query},
                ],
                history_disabled=True,
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"G4F API error: {e}")
            return None


if __name__ == "__main__":
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.config import Config, configure_logging

    configure_logging()

    API_PROVIDER = "g4f"
    # Select API based on configuration
    if API_PROVIDER.lower() == "groq":
        api_handler = GroqAPIHandler(api_key=Config.GROQ_API_KEY)
    elif API_PROVIDER.lower() == "openai":
        api_handler = OpenAIAPIHandler(api_key=Config.OPENAI_API_KEY)
    elif API_PROVIDER.lower() == "g4f":
        api_handler = g4fAPIHandler(cookies_dir=Config.COOKIES_DIR)
    else:
        raise ValueError("Unsupported API provider specified.")

    query = "What model am I talking with?"
    response = api_handler.get_response(query)
    if response:
        print(response)
    else:
        print("Failed to get a response.")

    # Example usage for Groq VLM API
    # Uncomment and set a valid image path and prompt to test the VLM method.
    # if API_PROVIDER.lower() == "groq":
    #     image_prompt = "What's in this image?"
    #     image_path = "sf.jpg"  # Replace with your image file path
    #     vlm_response = api_handler.get_vlm_response(image_prompt, image_path)
    #     if vlm_response:
    #         print(vlm_response)
    #     else:
    #         print("Failed to get a VLM response.")
