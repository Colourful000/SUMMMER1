from openai import OpenAI

client = OpenAI(
    api_key="sk-58530a01a7a94d66a92c010a8a86f0a9",
    base_url="https://api.deepseek.com"
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "你是一个友好的营养师"},
        {"role": "user", "content": "帮我分析一份披萨的营养价值，并给一点建议"}
    ]
)

print(response.choices[0].message.content)