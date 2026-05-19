import re


def parse_ingredients(text: str) -> list[dict]:
    """
    Парсит список ингредиентов из AI-ответа.
    """

    ingredients = []

    pattern = re.compile(
        r"[-•]\s*(?P<name>.+?)\s*[—-]\s*(?P<weight>\d+(?:[.,]\d+)?)\s*г",
        re.IGNORECASE,
    )

    for match in pattern.finditer(text):
        name = match.group("name").strip().lower()
        weight = float(match.group("weight").replace(",", "."))

        ingredients.append(
            {
                "name": name,
                "weight": weight,
            }
        )

    return ingredients