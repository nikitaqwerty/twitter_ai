import os
from groq import Groq


class GroqLLM:
    def __init__(self, api_key):
        self.client = Groq(api_key=api_key)

    def get_response(self, query, model="llama3-70b-8192"):
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[{"role": "user", "content": query}], model=model
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            print(f"An error occurred: {e}")
            return None


if __name__ == "__main__":
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.config import Config

    # Example usage
    groq_llm = GroqLLM(api_key=Config.GROQ_API_KEY)
    query = "Explain the importance of fast language models"
    response = groq_llm.get_response(query)
    if response:
        print(response)
    else:
        print("Failed to get a response.")
