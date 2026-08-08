"""Scraper de exito.com que envía los productos extraídos a la API."""
from __future__ import annotations

import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("exito-scraper")

BASE_URL = "https://www.exito.com"
API_URL = os.getenv("API_URL", "http://localhost:8000/api/items")
FUENTE = "exito.com"
DEFAULT_TIMEOUT = 25
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

SEL_GALERIA = (
    "ul[class*='product-grid_fs-product-grid'] li, "
    ".product-grid_fs-product-grid___qKN2 li"
)
SEL_NOMBRE = "h3.styles_name__qQJiK, [data-fs-product-card-title], h3"
SEL_PRECIO = "[data-fs-product-card-prices], [data-fs-container-price-otros]"
SEL_LINK = "a[data-testid='product-link'], a[href]"
SEL_IMG = "img"


@dataclass
class Producto:
    """Representa un producto extraído del catálogo."""

    nombre: str
    precio: Optional[str] = None
    precio_lista: Optional[str] = None
    url: Optional[str] = None
    imagen: Optional[str] = None


def a_numero(texto: Optional[str]) -> Optional[float]:
    """Convierte '$ 52.900' a 52900.0 usando el formato colombiano."""
    if not texto:
        return None
    limpio = re.sub(r"[^\d.,]", "", texto)
    if not limpio:
        return None
    limpio = limpio.replace(".", "").replace(",", ".")
    try:
        return float(limpio)
    except ValueError:
        return None


class ExitoScraper:
    """Encapsula un navegador Selenium para scrapear exito.com."""

    def __init__(self, headless: bool = True, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.driver = self._crear_driver(headless)
        self.wait = WebDriverWait(self.driver, timeout)

    def _crear_driver(self, headless: bool) -> webdriver.Chrome:
        """Configura y devuelve una instancia de Chrome WebDriver."""
        options = Options()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"--user-agent={USER_AGENT}")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        driver = webdriver.Chrome(options=options)
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": (
                    "Object.defineProperty(navigator, 'webdriver', "
                    "{get: () => undefined})"
                )
            },
        )
        return driver

    def abrir(self, url: str = BASE_URL) -> None:
        """Navega a una URL y espera a que cargue el body."""
        logger.info("Abriendo %s", url)
        self.driver.get(url)
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    def buscar(self, termino: str) -> str:
        """Busca un término y espera a que aparezca la grilla de productos."""
        url = f"{BASE_URL}/s?q={termino.replace(' ', '%20')}"
        self.abrir(url)
        self._aceptar_cookies()
        try:
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, SEL_GALERIA))
            )
        except TimeoutException:
            logger.warning("No apareció la grilla; puede que cambiara el selector")
        self._scroll_para_cargar()
        return url

    def _aceptar_cookies(self) -> None:
        """Cierra el banner de cookies si aparece."""
        selectores = [
            (By.ID, "onetrust-accept-btn-handler"),
            (By.CSS_SELECTOR, "button[aria-label*='aceptar' i]"),
        ]
        for by, selector in selectores:
            try:
                boton = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((by, selector))
                )
                boton.click()
                logger.info("Banner de cookies cerrado")
                return
            except TimeoutException:
                continue

    def _scroll_para_cargar(self, pasos: int = 6, pausa: float = 1.2) -> None:
        """Hace scroll progresivo para forzar la carga perezosa (lazy load)."""
        altura_previa = 0
        for _ in range(pasos):
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            time.sleep(pausa)
            altura_actual = self.driver.execute_script(
                "return document.body.scrollHeight"
            )
            if altura_actual == altura_previa:
                break
            altura_previa = altura_actual

    def extraer_productos(self) -> list[Producto]:
        """Extrae los productos de la página de resultados actual."""
        productos: list[Producto] = []
        tarjetas = self.driver.find_elements(By.CSS_SELECTOR, SEL_GALERIA)
        logger.info("Se encontraron %d tarjetas", len(tarjetas))

        for tarjeta in tarjetas:
            nombre = self._texto_opcional(tarjeta, SEL_NOMBRE)
            if not nombre:
                continue
            precio, precio_lista = self._parsear_precios(
                self._texto_opcional(tarjeta, SEL_PRECIO)
            )
            productos.append(
                Producto(
                    nombre=nombre,
                    precio=precio,
                    precio_lista=precio_lista,
                    url=self._atributo_opcional(tarjeta, SEL_LINK, "href"),
                    imagen=self._extraer_imagen(tarjeta),
                )
            )

        logger.info("Se extrajeron %d productos", len(productos))
        return productos

    def diagnostico_tarjeta(self, indice: int = 0) -> str:
        """Devuelve el HTML de una tarjeta para inspeccionar sus selectores."""
        tarjetas = self.driver.find_elements(By.CSS_SELECTOR, SEL_GALERIA)
        if not tarjetas:
            return "Sin tarjetas: revisa SEL_GALERIA."
        return tarjetas[indice].get_attribute("outerHTML")

    @staticmethod
    def _extraer_imagen(tarjeta) -> Optional[str]:
        """Obtiene la URL real de la imagen evitando placeholders base64.

        Con lazy load, src puede traer un GIF transparente embebido, así que
        se prueban primero data-src y srcset.
        """
        try:
            img = tarjeta.find_element(By.CSS_SELECTOR, SEL_IMG)
        except NoSuchElementException:
            return None

        for atributo in ("data-src", "srcset", "src"):
            valor = img.get_attribute(atributo)
            if not valor:
                continue
            if atributo == "srcset":
                valor = valor.split(",")[0].strip().split(" ")[0]
            valor = valor.strip()
            if valor and not valor.startswith("data:"):
                return valor
        return None

    @staticmethod
    def _parsear_precios(texto: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        """Separa el texto de precios en (precio_final, precio_lista).

        El bloque puede venir como '$ 52.900' o, con descuento,
        '-15%\\n$ 21.380\\n$ 18.173' (descuento, precio lista, precio final).
        """
        if not texto:
            return None, None
        montos = re.findall(r"\$\s?[\d.,]+", texto)
        montos = [m.replace(" ", "") for m in montos]
        if not montos:
            return None, None
        if len(montos) == 1:
            return montos[0], None
        return montos[-1], montos[0]

    @staticmethod
    def _texto_opcional(elemento, selector: str) -> Optional[str]:
        try:
            texto = elemento.find_element(By.CSS_SELECTOR, selector).text.strip()
            return texto or None
        except NoSuchElementException:
            return None

    @staticmethod
    def _atributo_opcional(elemento, selector: str, atributo: str) -> Optional[str]:
        try:
            valor = elemento.find_element(
                By.CSS_SELECTOR, selector
            ).get_attribute(atributo)
            return valor.strip() if valor else None
        except NoSuchElementException:
            return None

    def cerrar(self) -> None:
        """Cierra el navegador y libera recursos."""
        if self.driver:
            self.driver.quit()
            logger.info("Navegador cerrado")

    def __enter__(self) -> "ExitoScraper":
        return self

    def __exit__(self, *_) -> None:
        self.cerrar()


def construir_payload(productos: list[Producto], termino: str) -> list[dict]:
    """Empaqueta los productos en el formato que espera la tabla scraped_items."""
    payload: list[dict] = []
    vistos: set[str] = set()

    for p in productos:
        if not p.url:
            continue

        url = urljoin(BASE_URL, p.url)
        if urlparse(url).scheme not in ("http", "https"):
            continue
        if url in vistos:
            continue
        vistos.add(url)

        precio = a_numero(p.precio)
        lista = a_numero(p.precio_lista)

        descuento = None
        if precio is not None and lista is not None and lista > precio:
            descuento = round((lista - precio) / lista * 100, 2)

        payload.append(
            {
                "nombre": p.nombre,
                "url": url,
                "imagen": p.imagen,
                "precio": precio,
                "precio_lista": lista,
                "descuento_pct": descuento,
                "termino": termino,
                "fuente": FUENTE,
            }
        )

    return payload


def enviar_a_api(productos: list[Producto], termino: str) -> None:
    """Transmite los productos a la API central mediante una petición POST."""
    payload = construir_payload(productos, termino)

    if not payload:
        logger.warning("No hay productos válidos para enviar")
        return

    logger.info("Enviando %d productos a %s", len(payload), API_URL)
    try:
        respuesta = requests.post(API_URL, json=payload, timeout=30)
        respuesta.raise_for_status()
        logger.info("La API respondió: %s", respuesta.json())
    except requests.RequestException as error:
        logger.error("Falló el envío a la API: %s", error)


def main(termino: str = "arroz") -> None:
    """Ejecuta el ciclo completo: buscar, extraer y enviar."""
    with ExitoScraper(headless=True) as scraper:
        scraper.buscar(termino)
        productos = scraper.extraer_productos()
        enviar_a_api(productos, termino)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "arroz")