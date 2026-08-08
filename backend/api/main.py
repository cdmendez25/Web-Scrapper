"""API REST que conecta el scraper con la base de datos en Supabase."""
from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_KEY en el archivo .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(title="API de productos scrapeados")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Item(BaseModel):
    """Estructura que debe cumplir cada producto recibido del scraper."""

    nombre: str
    url: str
    imagen: str | None = None
    precio: float | None = None
    precio_lista: float | None = None
    descuento_pct: float | None = None
    termino: str | None = None
    fuente: str | None = None


@app.post("/api/items")
def crear_items(items: list[Item]):
    """Recibe la lista de productos y los inserta en Supabase."""
    if not items:
        raise HTTPException(status_code=400, detail="La lista de items está vacía")

    payload = [item.model_dump() for item in items]

    try:
        respuesta = (
            supabase.table("scraped_items")
            .upsert(payload, on_conflict="url")
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Error en Supabase: {error}")

    return {"insertados": len(respuesta.data)}


@app.get("/api/items")
def listar_items():
    """Devuelve todos los productos ordenados del más reciente al más antiguo."""
    try:
        respuesta = (
            supabase.table("scraped_items")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Error en Supabase: {error}")

    return respuesta.data