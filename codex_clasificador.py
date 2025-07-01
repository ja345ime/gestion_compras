from dotenv import load_dotenv
load_dotenv()

import os
import openai
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

prompt_sistema = open("/home/gestion_compras/prompts_codex/prompt_clasificador.txt", "r").read()
error = open("/tmp/error.txt").read().strip()

chat_completion = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": prompt_sistema},
        {"role": "user", "content": f"Error: {error}"}
    ]
)

categoria = chat_completion.choices[0].message.content.strip().lower()

with open("/tmp/categoria_codex.txt", "w") as f:
    f.write(categoria)

print(f"✅ Clasificación del error: {categoria}")
