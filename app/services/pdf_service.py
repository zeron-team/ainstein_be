from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML
import os

env = Environment(
    loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), '..', 'templates')),
    autoescape=select_autoescape()
)

def _render_html(epc: dict, payload: dict, brand: dict) -> str:
    tpl = env.get_template('epc_print.html')
    return tpl.render(epc=epc, p=payload, brand=brand)

async def render_epc_pdf(epc, payload, brand) -> bytes:
    html = _render_html(epc.__dict__, payload, brand.__dict__ if brand else {})
    pdf = HTML(string=html).write_pdf()
    return pdf
