import base64
import io
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from django.conf import settings


PNG_WIDTH = 564
PNG_HEIGHT = 157
SECRETARIA_FIXA = 'Secretaria de Parcerias em Investimentos'
ENDERECO_FIXO = 'Rua Iaiá, 126 - Itaim Bibi'
CIDADE_FIXA = 'São Paulo/SP - CEP 04542-906'
NAVY = '#000000'
TEXT = '#1f2937'


@lru_cache(maxsize=1)
def _font_paths():
    return {
        'regular': '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        'bold': '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    }


@lru_cache(maxsize=1)
def _template():
    path = Path(settings.BASE_DIR) / 'static' / 'assinatura_e_mail' / 'assets' / 'modelo_2026.png'
    return Image.open(path).convert('RGBA')


def _font(style, size):
    return ImageFont.truetype(_font_paths()[style], size=size)


def _fit_font(draw, text, max_width, max_height, style='regular', max_size=56, min_size=14, spacing=4):
    chosen = _font(style, min_size)
    for size in range(max_size, min_size - 1, -1):
        candidate = _font(style, size)
        box = draw.multiline_textbbox((0, 0), text, font=candidate, spacing=spacing)
        width = box[2] - box[0]
        height = box[3] - box[1]
        if width <= max_width and height <= max_height:
            return candidate
        chosen = candidate
    return chosen


def _draw_wrapped(draw, text, box, style='regular', max_size=56, min_size=14, fill=TEXT, align='left', spacing=4):
    x1, y1, x2, y2 = box
    max_width = x2 - x1
    max_height = y2 - y1
    words = (text or '').split()
    if not words:
        return

    lines = []
    current = words[0]
    base_font = _font(style, max_size)
    for word in words[1:]:
        trial = f'{current} {word}'
        width = draw.textbbox((0, 0), trial, font=base_font)[2]
        if width <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    joined = '\n'.join(lines)
    font = _fit_font(draw, joined, max_width, max_height, style=style, max_size=max_size, min_size=min_size, spacing=spacing)
    box_size = draw.multiline_textbbox((0, 0), joined, font=font, spacing=spacing, align=align)
    text_width = box_size[2] - box_size[0]
    text_height = box_size[3] - box_size[1]
    x = x1
    if align == 'center':
        x = x1 + max((max_width - text_width) / 2, 0)
    y = y1 + max((max_height - text_height) / 2, 0)
    draw.multiline_text((x, y), joined, font=font, fill=fill, spacing=spacing, align=align)


def _draw_single_line(draw, text, box, style='regular', max_size=24, min_size=10, fill=TEXT):
    x1, y1, x2, y2 = box
    max_width = x2 - x1
    max_height = y2 - y1
    font = _fit_font(draw, text, max_width, max_height, style=style, max_size=max_size, min_size=min_size)
    text_box = draw.textbbox((0, 0), text, font=font)
    text_height = text_box[3] - text_box[1]
    draw.text((x1, y1 + max((max_height - text_height) / 2, 0)), text, font=font, fill=fill)


def render_signature_png(data):
    image = _template().copy()
    draw = ImageDraw.Draw(image)

    # Preserva o lado esquerdo e toda a estrutura gráfica do modelo-base.
    # Redesenha somente os campos dinâmicos no bloco da direita.
    draw.rectangle((228, 10, 556, 95), fill='#ffffff')
    draw.rectangle((258, 104, 451, 149), fill='#ffffff')
    draw.rectangle((438, 104, 558, 121), fill='#ffffff')

    _draw_single_line(draw, data['nome_completo'], (236, 14, 550, 33), style='bold', max_size=19, min_size=10, fill=NAVY)
    _draw_single_line(draw, data['cargo_funcao'], (236, 33, 550, 47), style='regular', max_size=12, min_size=8, fill=TEXT)
    _draw_single_line(draw, SECRETARIA_FIXA, (236, 58, 550, 72), style='bold', max_size=11, min_size=8, fill=TEXT)
    _draw_single_line(draw, data.get('departamento') or '-', (236, 73, 550, 88), style='regular', max_size=11, min_size=8, fill=TEXT)
    _draw_single_line(draw, data['email'], (286, 106, 447, 118), style='regular', max_size=12, min_size=7, fill=TEXT)
    _draw_single_line(draw, f'(11) 3702-{(data.get("ramal") or "").strip() or "XXXX"}', (466, 106, 557, 118), style='regular', max_size=11, min_size=7, fill=TEXT)
    _draw_single_line(draw, ENDERECO_FIXO, (286, 120, 451, 133), style='regular', max_size=11, min_size=7, fill=TEXT)
    _draw_single_line(draw, CIDADE_FIXA, (286, 133, 451, 146), style='regular', max_size=11, min_size=7, fill=TEXT)

    output = io.BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


def png_data_uri(png_bytes):
    encoded = base64.b64encode(png_bytes).decode('ascii')
    return f'data:image/png;base64,{encoded}'
