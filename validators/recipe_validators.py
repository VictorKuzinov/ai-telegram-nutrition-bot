import re

from rapidfuzz import fuzz
from pymorphy3 import MorphAnalyzer

from config_ai import FORBIDDEN_PRODUCTS
from services.message_ai_parser import (
    parse_ingredients_recipe,
    RecipeIngredient,
    RecipeIngredients,
    extract_ingredients_block,
)
from services.recipe_utils import (
    extract_recipe_name,
    RECIPE_REQUIRED_PRODUCTS,
)

morph = MorphAnalyzer()

BAD_UNITS_MARKERS = [
    "шт",
    "ложк",
    "по вкусу",
    "щепотк",
    "стакан",
]


class RecipeValidationResult:
    def __init__(
        self,
        ingredients: RecipeIngredients,
        valid: bool = True,
        errors: list[str] | None = None,
        warnings: list[str] | None = None,
        missing_products: RecipeIngredients | None = None,
    ):
        self.ingredients = ingredients
        self.valid = valid
        self.errors = errors or []
        self.warnings = warnings or []
        self.missing_products = missing_products or []

    @property
    def is_valid(self) -> bool:
        return self.valid and not self.errors

    def add_error(self, message: str) -> None:
        self.errors.append(message)
        self.valid = False

    def add_warning(self, message: str)-> None:
        self.warnings.append(message)

    def add_missing_product(self, product: RecipeIngredient) -> None:
        self.missing_products.append(product)

def validate_recipe_structure(
    text: str,
    result: RecipeValidationResult,
) -> None:
    lowered = text.lower()

    if "название:" not in lowered:
        result.add_error("Не найден раздел 'Название'.")

    if "ингредиенты:" not in lowered:
        result.add_error("Не найден раздел 'Ингредиенты'.")

    if "приготовление:" not in lowered:
        result.add_error("Не найден раздел 'Приготовление'.")


def validate_recipe_ingredients(
    result: RecipeValidationResult,
) -> None:
    for item in result.ingredients:
        name = item["name"].strip().lower()

        for bad in FORBIDDEN_PRODUCTS:
            if (
                    name == bad
                    or name.startswith(bad + "(")
            ):
                result.add_error(
                    f"Неконкретный ингредиент: {item['name']}"
                )

        if "(" in name or ")" in name:
            result.add_error(
                f"Ингредиент содержит пояснение или варианты: {item['name']}"
            )
            result.valid = False

def validate_steps(
    text: str,
    result: RecipeValidationResult,
) -> None:
    lowered = text.lower()

    bad_phrases = [
        "нарежьте рис",
        "нарежьте гречку",
        "нарежьте макароны",
        "обжарьте до зеленого цвета",
        "форма для плова",
        "форму для плова",
        "форму для плюва",
        "обжарьте соль",
        "Залейте фарш виноградными листьями"
    ]

    match = re.search(
        r"приготовление:\s*(.*)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not match or not match.group(1).strip():
        result.add_error("Некорректная технология приготовления: пустой раздел'.")

    if lowered.strip().endswith((" до", " до\n")):
        result.add_error("Некорректная технология приготовления: рецепт обрывается.")

    for phrase in bad_phrases:
        if phrase in lowered:
            result.add_error(
                f"Некорректная технология приготовления: {phrase}"
            )
    steps = [
            line.strip()
            for line in text.splitlines()
            if re.match(r"^\d+\.", line.strip())
        ]

    normalized_steps = [
        re.sub(r"^\d+\.\s*", "", step).strip().lower()
        for step in steps
    ]

    seen = set()

    for step in normalized_steps:
        if step in seen:
            result.add_error(
                f"Некорректная технология приготовления: повтор шага '{step}'"
            )
        seen.add(step)

def validate_forbidden_phrases(
    text: str,
    result: RecipeValidationResult,
) -> None:
    pass

def validate_recipe_units(
    text: str,
    result: RecipeValidationResult,
) -> None:
    ingredients_block = extract_ingredients_block(text).lower()

    for marker in BAD_UNITS_MARKERS:
        if marker in ingredients_block:
            result.add_error(
                f"В ингредиентах использована запрещённая единица измерения: {marker}"
            )

def validate_required_ingredients(
    text: str,
    result: RecipeValidationResult,
) -> None:
    recipe_name = extract_recipe_name(text)

    if recipe_name is None:
        return

    recipe_name = recipe_name.lower().strip()

    required_groups = None

    for recipe_key, groups in RECIPE_REQUIRED_PRODUCTS.items():
        if recipe_key in recipe_name:
            required_groups = groups
            break

    if required_groups is None:
        return

    ingredients_block = extract_ingredients_block(text).lower()

    for group in required_groups:
        if not any(product in ingredients_block for product in group):
            result.add_error(
                f"В рецепте отсутствует один из обязательных ингредиентов: "
                f"{', '.join(group)}"
            )

# def validate_recipe_title(
#     text: str,
#     expected_title: str,
#     result: RecipeValidationResult,
# ) -> None:
#     recipe_title = extract_recipe_name(text)
#
#     if recipe_title is None:
#         result.add_error("Не найдено название рецепта.")
#         return
#
#     if expected_title.lower().strip() not in recipe_title.lower():
#         result.add_error(
#             f"Название рецепта не соответствует запросу: {recipe_title}"
#         )

def normalize_title(text: str) -> str:
    words = text.lower().replace("ё", "е").split()
    return " ".join(
        morph.parse(word)[0].normal_form
        for word in words
    )

def validate_recipe_title(
    expected_title: str,
    text: str,
    result: RecipeValidationResult,
) -> None:
    actual_title = extract_recipe_name(text)

    if actual_title is None:
        result.add_error("Не найдено название рецепта.")
        return

    expected = normalize_title(expected_title)
    actual = normalize_title(actual_title)

    score = fuzz.token_set_ratio(expected, actual)

    if score < 60:
        result.add_error(
            f"Название рецепта не соответствует запросу: ожидалось '{expected_title}', получено '{actual_title}'."
        )

def validate_recipe(text: str) -> RecipeValidationResult:
    result = RecipeValidationResult(
        ingredients=parse_ingredients_recipe(text)
    )
    validate_recipe_structure(text, result)
    validate_recipe_units(text, result)
    validate_recipe_ingredients(result)
    validate_required_ingredients(text, result)
    validate_steps(text, result)
    validate_forbidden_phrases(text, result)
    return result

