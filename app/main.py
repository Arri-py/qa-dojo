import os
import time
import uuid
from contextlib import contextmanager
from typing import Optional, Literal

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, HTTPException
from fastapi.routing import APIRouter
from pydantic import BaseModel

app = FastAPI(
    title="QA Dojo — Calculator API",
    description="Калькулятор с историей вычислений в PostgreSQL. Две версии API: v1 и v2.",
    version="3.0.0",
)

# ── database ──────────────────────────────────────────────────────────────────
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "calculator"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}


@contextmanager
def get_conn():
    conn = psycopg2.connect(**DB_CONFIG, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.on_event("startup")
def startup():
    for attempt in range(15):
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS calculations (
                            id          TEXT PRIMARY KEY,
                            operation   TEXT    NOT NULL,
                            a           FLOAT   NOT NULL,
                            b           FLOAT   NOT NULL,
                            result      FLOAT   NOT NULL,
                            expression  TEXT
                        )
                    """)
            return
        except psycopg2.OperationalError:
            time.sleep(2)
    raise RuntimeError("Не удалось подключиться к базе данных")


# ── helpers ───────────────────────────────────────────────────────────────────
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
        return a ** b
    raise HTTPException(400, f"Неизвестная операция: {operation}")


def _expression(op: str, a: float, b: float, result: float) -> str:
    return f"{a} {SYMBOLS.get(op, '?')} {b} = {result}"


def _insert(operation: str, a: float, b: float, expression: str | None = None) -> dict:
    result = _compute(operation, a, b)
    calc_id = str(uuid.uuid4())
    expr = expression or _expression(operation, a, b, result) if expression is not None else None
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO calculations (id, operation, a, b, result, expression) VALUES (%s, %s, %s, %s, %s, %s)",
                (calc_id, operation, a, b, result, expr),
            )
    return {"id": calc_id, "operation": operation, "a": a, "b": b, "result": result, "expression": expr}


def _fetch(calc_id: str) -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM calculations WHERE id = %s", (calc_id,))
            row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Вычисление не найдено")
    return dict(row)


def _fetch_all() -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM calculations ORDER BY id")
            return [dict(r) for r in cur.fetchall()]


def _update(calc_id: str, operation: str, a: float, b: float, expression: str | None = None) -> dict:
    result = _compute(operation, a, b)
    expr = expression if expression is not None else None
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE calculations SET operation=%s, a=%s, b=%s, result=%s, expression=%s WHERE id=%s",
                (operation, a, b, result, expr, calc_id),
            )
    return {"id": calc_id, "operation": operation, "a": a, "b": b, "result": result, "expression": expr}


def _delete(calc_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM calculations WHERE id = %s", (calc_id,))


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
    expression: Optional[str] = None


# ── v1 ────────────────────────────────────────────────────────────────────────
v1 = APIRouter(prefix="/api/v1", tags=["v1"])


@v1.get("/health")
def health_v1():
    return {"status": "ok", "version": "1"}


@v1.get("/operations")
def operations_v1():
    return {"operations": sorted(OPS_V1)}


@v1.post("/calculations", response_model=CalcResponse, status_code=201)
def create_v1(body: CalcRequestV1):
    return _insert(body.operation, body.a, body.b)


@v1.get("/calculations")
def list_v1():
    rows = _fetch_all()
    return {"calculations": rows, "total": len(rows)}


@v1.get("/calculations/{calc_id}", response_model=CalcResponse)
def get_v1(calc_id: str):
    return _fetch(calc_id)


@v1.put("/calculations/{calc_id}", response_model=CalcResponse)
def replace_v1(calc_id: str, body: CalcRequestV1):
    _fetch(calc_id)
    return _update(calc_id, body.operation, body.a, body.b)


@v1.patch("/calculations/{calc_id}", response_model=CalcResponse)
def patch_v1(calc_id: str, body: CalcPatch):
    record = _fetch(calc_id)
    op = body.operation or record["operation"]
    a = body.a if body.a is not None else record["a"]
    b = body.b if body.b is not None else record["b"]
    if op not in OPS_V1:
        raise HTTPException(400, f"Операция недоступна в v1: {op}")
    return _update(calc_id, op, a, b)


@v1.delete("/calculations/{calc_id}", status_code=204)
def delete_v1(calc_id: str):
    _fetch(calc_id)
    _delete(calc_id)


# ── v2 ────────────────────────────────────────────────────────────────────────
v2 = APIRouter(prefix="/api/v2", tags=["v2"])


@v2.get("/health")
def health_v2():
    return {"status": "ok", "version": "2"}


@v2.get("/operations")
def operations_v2():
    return {"operations": sorted(OPS_V2)}


@v2.post("/calculations", response_model=CalcResponseV2, status_code=201)
def create_v2(body: CalcRequestV2):
    result = _compute(body.operation, body.a, body.b)
    expr = _expression(body.operation, body.a, body.b, result)
    return _insert(body.operation, body.a, body.b, expression=expr)


@v2.get("/calculations")
def list_v2():
    rows = _fetch_all()
    return {"calculations": rows, "total": len(rows)}


@v2.get("/calculations/{calc_id}", response_model=CalcResponseV2)
def get_v2(calc_id: str):
    return _fetch(calc_id)


@v2.get("/calculations/{calc_id}/expression")
def expression_v2(calc_id: str):
    record = _fetch(calc_id)
    expr = record.get("expression") or _expression(record["operation"], record["a"], record["b"], record["result"])
    return {"expression": expr}


@v2.put("/calculations/{calc_id}", response_model=CalcResponseV2)
def replace_v2(calc_id: str, body: CalcRequestV2):
    _fetch(calc_id)
    result = _compute(body.operation, body.a, body.b)
    expr = _expression(body.operation, body.a, body.b, result)
    return _update(calc_id, body.operation, body.a, body.b, expression=expr)


@v2.patch("/calculations/{calc_id}", response_model=CalcResponseV2)
def patch_v2(calc_id: str, body: CalcPatch):
    record = _fetch(calc_id)
    op = body.operation or record["operation"]
    a = body.a if body.a is not None else record["a"]
    b = body.b if body.b is not None else record["b"]
    if op not in OPS_V2:
        raise HTTPException(400, f"Неизвестная операция: {op}")
    result = _compute(op, a, b)
    expr = _expression(op, a, b, result)
    return _update(calc_id, op, a, b, expression=expr)


@v2.delete("/calculations/{calc_id}", status_code=204)
def delete_v2(calc_id: str):
    _fetch(calc_id)
    _delete(calc_id)


# ── register ──────────────────────────────────────────────────────────────────
app.include_router(v1)
app.include_router(v2)
