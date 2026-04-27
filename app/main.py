from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="QA Dojo Calculator",
    description="Калькулятор для первой каты. Изучи эндпоинты и напиши свой клиент!",
    version="1.0.0",
)


class Numbers(BaseModel):
    a: float
    b: float


class Result(BaseModel):
    result: float


@app.get("/health", tags=["service"])
def health():
    return {"status": "ok"}


@app.post("/add", response_model=Result, tags=["calculator"], summary="Сложение")
def add(numbers: Numbers):
    return {"result": numbers.a + numbers.b}


@app.post("/subtract", response_model=Result, tags=["calculator"], summary="Вычитание")
def subtract(numbers: Numbers):
    return {"result": numbers.a - numbers.b}


@app.post("/multiply", response_model=Result, tags=["calculator"], summary="Умножение")
def multiply(numbers: Numbers):
    return {"result": numbers.a * numbers.b}


@app.post("/divide", response_model=Result, tags=["calculator"], summary="Деление")
def divide(numbers: Numbers):
    if numbers.b == 0:
        raise HTTPException(status_code=400, detail="На ноль делить нельзя")
    return {"result": numbers.a / numbers.b}
