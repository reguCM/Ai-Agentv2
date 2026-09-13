from ollama import chat

response = chat(
    model="qwen3:8b",
    messages=[
        {
            "role": "user",
            "content": "こんにちは。簡単に自己紹介してください。"
        }
    ],
)

print(response.message.content)