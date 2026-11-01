"""JSON Schema de la salida estructurada que se le pide al proveedor.

Se deriva del contrato (`PlanProposal`) y se reduce al subconjunto que aceptan los dos
proveedores en modo estricto: sin `$ref`, uniones como `anyOf`, todas las propiedades
requeridas (las opcionales admiten `null`) y sin títulos ni descripciones, así lo único
que instruye al modelo es la plantilla versionada.

Lo que se descarta (largos de texto, patrón de los códigos) lo sigue exigiendo la
validación estricta del servicio: el esquema guía al modelo, no reemplaza al contrato.
"""

from app.schemas.plan_proposal import PlanProposal

_KEPT = {"type", "additionalProperties", "enum", "minItems", "maxItems"}


def response_schema(exclude: frozenset[str] = frozenset()) -> dict:
    """`exclude`: palabras clave que un proveedor no acepta, además de las descartadas."""
    schema = PlanProposal.model_json_schema()
    return _strict(schema, schema.get("$defs", {}), _KEPT - exclude)


def _strict(node: dict, defs: dict, kept: set[str]) -> dict:
    if "$ref" in node:
        return _strict(defs[node["$ref"].removeprefix("#/$defs/")], defs, kept)

    result = {}
    for key, value in node.items():
        if key in ("anyOf", "oneOf"):
            result["anyOf"] = [_strict(option, defs, kept) for option in value]
        elif key == "const":
            result["enum"] = [value]
        elif key == "properties":
            result["properties"] = {name: _strict(prop, defs, kept) for name, prop in value.items()}
            result["required"] = list(value)
        elif key == "items":
            result["items"] = _strict(value, defs, kept)
        elif key in kept:
            result[key] = value
    if result.get("type") == "object":
        result["additionalProperties"] = False
    return result


RESPONSE_SCHEMA = response_schema()
