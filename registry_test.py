import json

with open("registry/tools.json", "r", encoding="utf-8") as f:
    registry = json.load(f)

print("登録されているTool:")

for tool in registry["tools"]:
    print(f"- {tool['name']}")
    print(f"  category: {tool['category']}")
    print(f"  subcategory: {tool['subcategory']}")
    print(f"  description: {tool['description']}")