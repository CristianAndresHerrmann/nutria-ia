import json
from enum import StrEnum

from app.providers.base import (
    ProviderFailureError,
    ProviderOutput,
    ProviderTimeoutError,
)
from app.schemas.plan_proposal import FoodCategoryType, MealType, PlanProposalRequest


class FakeScenario(StrEnum):
    ok = "ok"
    invalid_output = "invalid_output"
    timeout = "timeout"
    provider_error = "provider_error"


# Categorías que arman cada opción, en orden. Solo sirven para que la propuesta
# simulada se parezca a un plan: no es una regla de composición (eso es del backend).
_MEAL_CATEGORIES = {
    MealType.breakfast: [FoodCategoryType.infusion, FoodCategoryType.carbohydrate, FoodCategoryType.fiber],
    MealType.afternoon_snack: [FoodCategoryType.infusion, FoodCategoryType.carbohydrate, FoodCategoryType.fiber],
    MealType.lunch: [FoodCategoryType.protein, FoodCategoryType.carbohydrate, FoodCategoryType.vegetable],
    MealType.dinner: [FoodCategoryType.protein, FoodCategoryType.carbohydrate, FoodCategoryType.vegetable],
}

_SIMULATED = "[Propuesta simulada]"


class FakeProvider:
    """Proveedor determinístico para validar el flujo sin llamar a un proveedor
    externo (riesgo 11). La misma solicitud da siempre la misma respuesta, y el
    escenario permite provocar cada error controlado.
    """

    name = "fake"
    model = "fake-deterministic"

    def __init__(self, scenario: str = FakeScenario.ok):
        self.scenario = FakeScenario(scenario)

    async def generate(self, prompt: str, request: PlanProposalRequest) -> ProviderOutput:
        if self.scenario is FakeScenario.timeout:
            raise ProviderTimeoutError("Timeout simulado")
        if self.scenario is FakeScenario.provider_error:
            raise ProviderFailureError("Falla simulada del proveedor")

        proposal = simulated_proposal(request)
        if self.scenario is FakeScenario.invalid_output:
            # Una cantidad es justo lo que el contrato no admite (RF-35).
            proposal["meals"][0]["calories"] = 1800
        return ProviderOutput(text=json.dumps(proposal, ensure_ascii=False))


def simulated_proposal(request: PlanProposalRequest) -> dict:
    return {
        "situational_diagnosis": f"{_SIMULATED} Diagnóstico situacional a completar por el profesional.",
        "introduction": f"{_SIMULATED} Introducción del plan alimentario.",
        "objectives": f"{_SIMULATED} Objetivos acordados en la consulta.",
        "general_recommendations": f"{_SIMULATED} Recomendaciones generales.",
        "contextual_recommendations": f"{_SIMULATED} Recomendaciones según el contexto de cocina y trabajo.",
        "thematic_recommendations": f"{_SIMULATED} Recomendaciones temáticas.",
        "meals": [_meal(meal_type, request) for meal_type in request.meal_types],
    }


def _meal(meal_type: MealType, request: PlanProposalRequest) -> dict:
    options = [_option(meal_type, request, index) for index in range(2)]
    recipe = next((r for r in request.candidate_recipes if meal_type in r.meal_types), None)
    if recipe:
        options.append({"description": "Opción con receta", "items": [{"type": "recipe", "code": recipe.code}]})
    if meal_type is request.meal_types[0]:
        options[0]["items"].append({"type": "free_text", "text": "Agua"})

    instructions = None
    if meal_type is MealType.breakfast:
        instructions = "Si no hay tiempo antes de salir, puede repartirse en dos momentos de la mañana."
    return {"meal_type": meal_type.value, "instructions": instructions, "options": options}


def _option(meal_type: MealType, request: PlanProposalRequest, index: int) -> dict:
    items = []
    for category in _MEAL_CATEGORIES[meal_type]:
        foods = [food for food in request.catalog.foods if category in food.categories]
        if foods:
            items.append({"type": "food", "code": foods[index % len(foods)].code})
    if index == 1 and request.catalog.food_groups:
        items.append({"type": "food_group", "code": request.catalog.food_groups[0].code})
    if not items:
        items.append({"type": "food", "code": request.catalog.foods[index % len(request.catalog.foods)].code})
    return {"description": f"Opción {index + 1}", "items": _without_repeats(items)}


def _without_repeats(items: list[dict]) -> list[dict]:
    unique = []
    for item in items:
        if item not in unique:
            unique.append(item)
    return unique
