from fastapi import FastAPI, HTTPException
from fastapi.routing import APIRouter
from pydantic import BaseModel
from typing import Optional, Literal
import uuid

app = FastAPI(
    title="QA Dojo — Calculator API",
    description="Калькулятор с историей вычислений. Две версии API: v1 и v2.",
    version="2.0.0",
)

# ── in-memory storage ─────────────────────────────────────────────────────────
_db: dict[str, dict] = {}

OPS_V1 = {"add", "subtract", "multiply", "divide"}
OPS_V2 = OPS_V1 | {"modulo", "power"}
SYMBOLS = {"add": "+", "subtract": "−", "multiply": "×", "divide": "÷", "modulo": "%", "power": "^"}


def _compute(operation: str, a: float, b: float) -> float:
    if operation == "add":
        return a + b
    if operation == "subtract":
        return a - b
    if operation == "multiply":
        return a * b
    if operation == "divide":
        if b == 0:
            raise HTTPException(400, "На ноль делить нельзя")
        return a / b
    if operation == "modulo":
        if b == 0:
            raise HTTPException(400, "На ноль делить нельзя")
        return a % b
    if operation == "power":
        return a**b
    raise HTTPException(400, f"Неизвестная операция: {operation}")


def _expression(op: str, a: float, b: float, result: float) -> str:
    return f"{a} {SYMBOLS.get(op, '?')} {b} = {result}"


# ── models ────────────────────────────────────────────────────────────────────
class CalcRequestV1(BaseModel):
    operation: Literal["add", "subtract", "multiply", "divide"]
    a: float
    b: float


class CalcRequestV2(BaseModel):
    operation: Literal["add", "subtract", "multiply", "divide", "modulo", "power"]
    a: float
    b: float


class CalcPatch(BaseModel):
    operation: Optional[str] = None
    a: Optional[float] = None
    b: Optional[float] = None


class CalcResponse(BaseModel):
    id: str
    operation: str
    a: float
    b: float
    result: float


class CalcResponseV2(CalcResponse):
    expression: str


# ── v1 ────────────────────────────────────────────────────────────────────────
v1 = APIRouter(prefix="/api/v1", tags=["v1"])


@v1.get("/health", summary="Проверка состояния сервиса")
def health_v1():
    return {"status": "ok", "version": "1"}


@v1.get("/operations", summary="Список доступных операций")
def operations_v1():
    return {"operations": sorted(OPS_V1)}


@v1.post("/calculations", response_model=CalcResponse, status_code=201, summary="Создать вычисление")
def create_v1(body: CalcRequestV1):
    calc_id = str(uuid.uuid4())
    result = _compute(body.operation, body.a, body.b)
    record = {"id": calc_id, "operation": body.operation, "a": body.a, "b": body.b, "result": result}
    _db[calc_id] = record
    return record


@v1.get("/calculations", summary="История всех вычислений")
def list_v1():
    return {"calculations": list(_db.values()), "total": len(_db)}


@v1.get("/calculations/{calc_id}", response_model=CalcResponse, summary="Получить вычисление по ID")
def get_v1(calc_id: str):
    if calc_id not in _db:
        raise HTTPException(404, "Вычисление не найдено")
    return _db[calc_id]


@v1.put("/calculations/{calc_id}", response_model=CalcResponse, summary="Заменить вычисление (все поля)")
def replace_v1(calc_id: str, body: CalcRequestV1):
    if calc_id not in _db:
        raise HTTPException(404, "Вычисление не найдено")
    result = _compute(body.operation, body.a, body.b)
    _db[calc_id] = {"id": calc_id, "operation": body.operation, "a": body.a, "b": body.b, "result": result}
    return _db[calc_id]


@v1.patch("/calculations/{calc_id}", response_model=CalcResponse, summary="Обновить вычисление частично")
def patch_v1(calc_id: str, body: CalcPatch):
    if calc_id not in _db:
        raise HTTPException(404, "Вычисление не найдено")
    record = _db[calc_id].copy()
    if body.operation is not None:
        if body.operation not in OPS_V1:
            raise HTTPException(400, f"Операция недоступна в v1: {body.operation}")
        record["operation"] = body.operation
    if body.a is not None:
        record["a"] = body.a
    if body.b is not None:
        record["b"] = body.b
    record["result"] = _compute(record["operation"], record["a"], record["b"])
    _db[calc_id] = record
    return record


@v1.delete("/calculations/{calc_id}", status_code=204, summary="Удалить вычисление")
def delete_v1(calc_id: str):
    if calc_id not in _db:
        raise HTTPException(404, "Вычисление не найдено")
    del _db[calc_id]


# ── v2 ────────────────────────────────────────────────────────────────────────
v2 = APIRouter(prefix="/api/v2", tags=["v2"])


@v2.get("/health", summary="Проверка состояния сервиса")
def health_v2():
    return {"status": "ok", "version": "2"}


@v2.get("/operations", summary="Список доступных операций")
def operations_v2():
    return {"operations": sorted(OPS_V2)}


@v2.post("/calculations", response_model=CalcResponseV2, status_code=201, summary="Создать вычисление")
def create_v2(body: CalcRequestV2):
    calc_id = str(uuid.uuid4())
    result = _compute(body.operation, body.a, body.b)
    record = {
        "id": calc_id,
        "operation": body.operation,
        "a": body.a,
        "b": body.b,
        "result": result,
        "expression": _expression(body.operation, body.a, body.b, result),
    }
    _db[calc_id] = record
    return record


@v2.get("/calculations", summary="История всех вычислений")
def list_v2():
    return {"calculations": list(_db.values()), "total": len(_db)}


@v2.get("/calculations/{calc_id}", response_model=CalcResponseV2, summary="Получить вычисление по ID")
def get_v2(calc_id: str):
    if calc_id not in _db:
        raise HTTPException(404, "Вычисление не найдено")
    record = _db[calc_id]
    if "expression" not in record:
        record["expression"] = _expression(record["operation"], record["a"], record["b"], record["result"])
    return record


@v2.get("/calculations/{calc_id}/expression", summary="Получить вычисление в виде строки")
def expression_v2(calc_id: str):
    if calc_id not in _db:
        raise HTTPException(404, "Вычисление не найдено")
    r = _db[calc_id]
    return {"expression": r.get("expression") or _expression(r["operation"], r["a"], r["b"], r["result"])}


@v2.put("/calculations/{calc_id}", response_model=CalcResponseV2, summary="Заменить вычисление (все поля)")
def replace_v2(calc_id: str, body: CalcRequestV2):
    if calc_id not in _db:
        raise HTTPException(404, "Вычисление не найдено")
    result = _compute(body.operation, body.a, body.b)
    _db[calc_id] = {
        "id": calc_id,
        "operation": body.operation,
        "a": body.a,
        "b": body.b,
        "result": result,
        "expression": _expression(body.operation, body.a, body.b, result),
    }
    return _db[calc_id]


@v2.patch("/calculations/{calc_id}", response_model=CalcResponseV2, summary="Обновить вычисление частично")
def patch_v2(calc_id: str, body: CalcPatch):
    if calc_id not in _db:
        raise HTTPException(404, "Вычисление не найдено")
    record = _db[calc_id].copy()
    if body.operation is not None:
        if body.operation not in OPS_V2:
            raise HTTPException(400, f"Неизвестная операция: {body.operation}")
        record["operation"] = body.operation
    if body.a is not None:
        record["a"] = body.a
    if body.b is not None:
        record["b"] = body.b
    record["result"] = _compute(record["operation"], record["a"], record["b"])
    record["expression"] = _expression(record["operation"], record["a"], record["b"], record["result"])
    _db[calc_id] = record
    return record


@v2.delete("/calculations/{calc_id}", status_code=204, summary="Удалить вычисление")
def delete_v2(calc_id: str):
    if calc_id not in _db:
        raise HTTPException(404, "Вычисление не найдено")
    del _db[calc_id]


# ── register routers ──────────────────────────────────────────────────────────
app.include_router(v1)
app.include_router(v2)
