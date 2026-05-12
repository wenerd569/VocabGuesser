import os
from groq import Groq

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY not set")
        _client = Groq(api_key=api_key)
    return _client


def ask(prompt: str, system: str = "You are a helpful assistant.", model: str = "llama-3.3-70b-versatile") -> str:
    """Send a single prompt and return the text response."""
    response = _get_client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    result = ask("Give me one example sentence using the word 'ephemeral'.")
    print(result)
