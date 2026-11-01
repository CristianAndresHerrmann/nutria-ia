"""Contrato de POST /plan-proposals.

La entrada es el contexto anonimizado que arma el backend: ningún modelo admite
campos fuera de los declarados (extra="forbid"), así un dato identificatorio que se
cuele da 422 antes de llegar al proveedor (RNF-07). La salida es la propuesta tal
como la mapea el backend sobre plan → comidas → opciones → ítems (DA-27), sin
cantidades, gramos ni calorías (RF-35).
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

# Los enums replican los de schema.prisma de nutria-backend.


class MealType(StrEnum):
    breakfast = "breakfast"
    lunch = "lunch"
    afternoon_snack = "afternoon_snack"
    dinner = "dinner"


class ConditionType(StrEnum):
    pathology = "pathology"
    allergy = "allergy"
    intolerance = "intolerance"
    rejection = "rejection"
    preference = "preference"


class FoodCategoryType(StrEnum):
    protein = "protein"
    carbohydrate = "carbohydrate"
    fiber = "fiber"
    vegetable = "vegetable"
    healthy_fat = "healthy_fat"
    infusion = "infusion"
    complementary = "complementary"


class CookingMethod(StrEnum):
    oven = "oven"
    stovetop = "stovetop"
    microwave = "microwave"
    no_cooking = "no_cooking"


# Códigos cortos que asigna el backend a cada elemento del catálogo enviado. El
# servicio no conoce los UUID: el backend traduce de vuelta.
Code = Annotated[str, StringConstraints(min_length=1, max_length=16, pattern=r"^[A-Za-z0-9_-]+$")]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
ContextText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
ProposalText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
ItemText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Entrada ---------------------------------------------------------------------


class Condition(ContractModel):
    """Condición del paciente, solo con el nombre de la patología, alimento o grupo.

    Las observaciones no viajan: son texto libre y pueden traer datos personales.
    """

    type: ConditionType
    name: Name


class CookingContext(ContractModel):
    """Contexto de cocina (RF-08)."""

    cooks: bool | None = None
    likes_cooking: bool | None = None
    cooking_time: ContextText | None = None
    home_equipment: ContextText | None = None
    usual_shopping_place: ContextText | None = None


class OutsideHomeContext(ContractModel):
    """Comidas fuera del hogar y medios para conservarlas o calentarlas (RF-09)."""

    meals_outside_home: ContextText | None = None
    outside_equipment: ContextText | None = None


class WorkContext(ContractModel):
    """Ocupación y contexto laboral, con regularidad de horarios (RF-10)."""

    occupation: ContextText | None = None
    work_context: ContextText | None = None


class Habits(ContractModel):
    """Hábitos (RF-06)."""

    physical_activity: ContextText | None = None
    smoking: ContextText | None = None
    alcohol: ContextText | None = None
    meal_schedule: ContextText | None = None
    sleep_schedule: ContextText | None = None


class CatalogFoodGroup(ContractModel):
    code: Code
    name: Name


class CatalogFood(ContractModel):
    code: Code
    name: Name
    group_code: Code
    categories: list[FoodCategoryType] = Field(default_factory=list, max_length=7)


class Catalog(ContractModel):
    """Subconjunto del catálogo permitido para el paciente, ya sin los alimentos
    rechazados (RF-37). Lo arma el backend."""

    food_groups: list[CatalogFoodGroup] = Field(default_factory=list, max_length=500)
    foods: list[CatalogFood] = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def _codes_are_consistent(self):
        _ensure_unique([group.code for group in self.food_groups], "food_groups")
        _ensure_unique([food.code for food in self.foods], "foods")
        group_codes = {group.code for group in self.food_groups}
        unknown = sorted({food.group_code for food in self.foods} - group_codes)
        if unknown:
            raise ValueError(f"group_code sin grupo en food_groups: {', '.join(unknown)}")
        return self


class CandidateRecipe(ContractModel):
    code: Code
    name: Name
    meal_types: list[MealType] = Field(min_length=1, max_length=4)
    cooking_method: CookingMethod | None = None
    time_minutes: int | None = Field(default=None, gt=0, le=1440)


PLAN_PROPOSAL_REQUEST_EXAMPLE = {
    "meal_types": ["breakfast", "lunch", "afternoon_snack", "dinner"],
    "conditions": [
        {"type": "pathology", "name": "Celiaquía"},
        {"type": "preference", "name": "Pescado"},
    ],
    "cooking": {
        "cooks": True,
        "likes_cooking": False,
        "cooking_time": "30 minutos por día",
        "home_equipment": "Horno y microondas",
        "usual_shopping_place": "Supermercado del barrio",
    },
    "outside_home": {
        "meals_outside_home": "Almuerza en el trabajo",
        "outside_equipment": "Heladera y microondas",
    },
    "work": {"occupation": "Empleo administrativo", "work_context": "Horario fijo de 8 a 16"},
    "habits": {
        "physical_activity": "Camina 30 minutos tres veces por semana",
        "smoking": "No fuma",
        "alcohol": "Ocasional",
        "meal_schedule": "Desayuno 7, almuerzo 13, merienda 17, cena 21",
        "sleep_schedule": "De 23 a 6:30",
    },
    "catalog": {
        "food_groups": [
            {"code": "G1", "name": "Frutas"},
            {"code": "G2", "name": "Verduras"},
            {"code": "G3", "name": "Carnes"},
            {"code": "G4", "name": "Cereales sin TACC"},
            {"code": "G5", "name": "Lácteos"},
            {"code": "G6", "name": "Infusiones"},
        ],
        "foods": [
            {"code": "A1", "name": "Manzana", "group_code": "G1", "categories": ["fiber"]},
            {"code": "A2", "name": "Zanahoria", "group_code": "G2", "categories": ["vegetable", "fiber"]},
            {"code": "A3", "name": "Zapallito", "group_code": "G2", "categories": ["vegetable"]},
            {"code": "A4", "name": "Pollo", "group_code": "G3", "categories": ["protein"]},
            {"code": "A5", "name": "Merluza", "group_code": "G3", "categories": ["protein"]},
            {"code": "A6", "name": "Arroz", "group_code": "G4", "categories": ["carbohydrate"]},
            {"code": "A7", "name": "Yogur natural", "group_code": "G5", "categories": ["protein"]},
            {"code": "A8", "name": "Té", "group_code": "G6", "categories": ["infusion"]},
        ],
    },
    "candidate_recipes": [
        {
            "code": "R1",
            "name": "Tarta de verduras sin TACC",
            "meal_types": ["lunch", "dinner"],
            "cooking_method": "oven",
            "time_minutes": 40,
        }
    ],
}


class PlanProposalRequest(ContractModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [PLAN_PROPOSAL_REQUEST_EXAMPLE]})

    meal_types: list[MealType] = Field(min_length=1, max_length=4)
    conditions: list[Condition] = Field(default_factory=list, max_length=100)
    cooking: CookingContext = Field(default_factory=CookingContext)
    outside_home: OutsideHomeContext = Field(default_factory=OutsideHomeContext)
    work: WorkContext = Field(default_factory=WorkContext)
    habits: Habits = Field(default_factory=Habits)
    catalog: Catalog
    candidate_recipes: list[CandidateRecipe] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def _no_repeats(self):
        _ensure_unique(self.meal_types, "meal_types")
        _ensure_unique([recipe.code for recipe in self.candidate_recipes], "candidate_recipes")
        return self


def _ensure_unique(values, field):
    repeated = sorted({str(value) for value in values if values.count(value) > 1})
    if repeated:
        raise ValueError(f"{field} tiene valores repetidos: {', '.join(repeated)}")


# --- Salida ----------------------------------------------------------------------


class FoodItem(ContractModel):
    type: Literal["food"]
    code: Code


class FoodGroupItem(ContractModel):
    """Referencia genérica, como "una fruta"."""

    type: Literal["food_group"]
    code: Code


class RecipeItem(ContractModel):
    type: Literal["recipe"]
    code: Code


class FreeTextItem(ContractModel):
    """Lo que el modelo no encontró en el catálogo. El backend lo guarda como ítem no
    reconocido con el texto original (DA-26)."""

    type: Literal["free_text"]
    text: ItemText


ProposalItem = Annotated[FoodItem | FoodGroupItem | RecipeItem | FreeTextItem, Field(discriminator="type")]


class ProposedOption(ContractModel):
    description: ShortText | None = None
    items: list[ProposalItem] = Field(min_length=1, max_length=15)


class ProposedMeal(ContractModel):
    meal_type: MealType
    # Fraccionamiento como indicación textual al paciente (RF-36).
    instructions: ShortText | None = None
    options: list[ProposedOption] = Field(min_length=1, max_length=10)


class ContractViolation(BaseModel):
    loc: list[str | int]
    msg: str


class PlanProposal(ContractModel):
    """Propuesta del modelo (RF-34). Las recomendaciones clínicas no están: salen del
    catálogo que elige el profesional (DA-16), no las redacta la IA (DA-28)."""

    situational_diagnosis: ProposalText
    introduction: ProposalText
    objectives: ProposalText
    general_recommendations: ProposalText
    contextual_recommendations: ProposalText
    thematic_recommendations: ProposalText
    meals: list[ProposedMeal] = Field(min_length=1, max_length=4)

    def violations_against(self, request: PlanProposalRequest) -> list[ContractViolation]:
        """Lo que la propuesta no puede tener respecto de la solicitud que la originó:
        comidas distintas de las pedidas y códigos que no se enviaron."""
        violations = []
        seen = []
        for meal_index, meal in enumerate(self.meals):
            if meal.meal_type in seen:
                violations.append(_violation(["meals", meal_index, "meal_type"], "Tipo de comida repetido"))
            elif meal.meal_type not in request.meal_types:
                violations.append(_violation(["meals", meal_index, "meal_type"], "Tipo de comida no solicitado"))
            seen.append(meal.meal_type)
        missing = [meal_type.value for meal_type in request.meal_types if meal_type not in seen]
        if missing:
            violations.append(_violation(["meals"], f"Faltan tipos de comida solicitados: {', '.join(missing)}"))

        known_codes = {
            "food": {food.code for food in request.catalog.foods},
            "food_group": {group.code for group in request.catalog.food_groups},
            "recipe": {recipe.code for recipe in request.candidate_recipes},
        }
        for meal_index, meal in enumerate(self.meals):
            for option_index, option in enumerate(meal.options):
                for item_index, item in enumerate(option.items):
                    if item.type != "free_text" and item.code not in known_codes[item.type]:
                        violations.append(
                            _violation(
                                ["meals", meal_index, "options", option_index, "items", item_index, "code"],
                                f"Código {item.code} no está entre los de tipo {item.type} enviados",
                            )
                        )
        return violations


def _violation(loc, msg):
    return ContractViolation(loc=loc, msg=msg)


class GenerationInfo(BaseModel):
    """Datos de la llamada al proveedor que el backend registra en ai_generation
    (RF-41, RNF-11)."""

    provider: str
    model: str
    template_version: str
    duration_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = Field(default=None, description="Incluye los tokens de razonamiento.")
    reasoning_tokens: int | None = Field(
        default=None,
        description="Parte de output_tokens que el modelo usó para razonar. Null si el proveedor no la informa.",
    )
    raw_response: str | None = Field(
        default=None, description="Respuesta cruda del proveedor. Null solo si no respondió (timeout o falla)."
    )


class PlanProposalResponse(BaseModel):
    proposal: PlanProposal
    generation: GenerationInfo


# --- Errores controlados ---------------------------------------------------------


class GenerationErrorCode(StrEnum):
    provider_timeout = "PROVIDER_TIMEOUT"
    provider_error = "PROVIDER_ERROR"
    invalid_provider_output = "INVALID_PROVIDER_OUTPUT"


class GenerationErrorDetails(BaseModel):
    generation: GenerationInfo
    errors: list[ContractViolation] | None = Field(
        default=None, description="Solo en INVALID_PROVIDER_OUTPUT: qué parte de la respuesta no respeta el contrato."
    )


class GenerationErrorBody(BaseModel):
    code: GenerationErrorCode
    message: str
    details: GenerationErrorDetails


class GenerationErrorResponse(BaseModel):
    """Mismo formato que los errores del backend: { error: { code, message, details } }."""

    error: GenerationErrorBody
