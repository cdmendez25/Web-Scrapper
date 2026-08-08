# Web-Scrapper

Busca productos en exito.com, los guarda en Supabase y los muestra en una página web.

Hecho por **Carlos Andrés Díaz Méndez**.

## Qué necesitas

Python 3.11+, Google Chrome y una cuenta de Supabase.

## Instalar

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

Crea un archivo `.env` en la raíz:

```
SUPABASE_URL="https://tu-proyecto.supabase.co"
SUPABASE_KEY="tu-service-key"
```

La URL va sin `/rest/v1/` al final.

En el SQL Editor de Supabase, crea la tabla:

```sql
create table scraped_items (
  id bigint generated always as identity primary key,
  created_at timestamptz default now(),
  nombre text, url text, imagen text,
  precio numeric, precio_lista numeric, descuento_pct numeric,
  moneda text default 'COP', termino text, fuente text
);

create unique index on scraped_items (url);
grant select, insert, update on scraped_items to service_role;
```

## Usar

Abre dos terminales.

**1. Prende la API** y déjala corriendo:

```bash
./venv/bin/uvicorn api.main:app --reload
```

**2. Corre el scraper** con lo que quieras buscar:

```bash
./venv/bin/python scripts/scraper.py arroz
```

**3. Mira los resultados** en http://localhost:5500:

```bash
./venv/bin/python -m http.server 5500 --directory frontend
```

## Archivos

- `scripts/scraper.py` — saca los productos de exito.com
- `api/main.py` — guarda y devuelve los productos
- `frontend/index.html` — la página que los muestra
