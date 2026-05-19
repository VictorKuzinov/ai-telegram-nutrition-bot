from pathlib import Path

from ai.gigachat_photo import (
    get_access_token,
    call_gigachat_vision,
)
from services.message_ai_parser import parse_ingredients

image_path = Path("picture/uploads/Плов.jpg")

print("Файл существует:", image_path.exists())

access_token = get_access_token()
content = call_gigachat_vision(image_path, access_token)
ingredients = parse_ingredients(content)

print(ingredients)
