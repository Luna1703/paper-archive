# Tigran Solomon's Paper Archive

Инструмент аналоговой визуальной стилизации фотографий под два архивных формата:
1. **Mode A — Receipt Archive**: 1-битный дизеринг (Floyd–Steinberg / Atkinson), верстка термального чека (580px / 800px), QR-код, уникальный индекс архива `ARC-{timestamp}-{random4}` и зубчатые перфорированные края.
2. **Mode B — Polaroid Snap**: Эмуляция мгновенной плёнки (Polaroid SX-70 / 600), цветовые кривые выцветания, виньетирование, плёночное зерно, органические утечки света (light leaks), аутентичная бумажная рамка с рукописной подписью и светящаяся дата 90-х на 7-сегментном LCD/LED дисплее (`YY MM DD`).

---

## Структура проекта

```text
projecct 1/
├── assets/
│   └── fonts/
│       ├── VT323-Regular.ttf          # Моноширинный пиксельный шрифт для чеков
│       ├── PressStart2P-Regular.ttf   # Альтернативный пиксельный шрифт
│       └── Caveat-Regular.ttf         # Рукописный шрифт для полароидной подписи
├── image_loader.py                    # Валидация формата, загрузка и нормализация (non-destructive)
├── receipt_processor.py               # Mode A: Floyd-Steinberg, гистограммный контраст, термо-чек
├── polaroid_processor.py              # Mode B: Polaroid-кривые, зерно, виньетка, light leak, LCD-штамп
├── main.py                            # Единая точка входа, функция process_image() и CLI-интерфейс
└── requirements.txt                   # Зависимости: Pillow, numpy, opencv-python, qrcode[pil]
```

---

## Установка

```bash
# Установка зависимостей
pip install -r requirements.txt
```

---

## Использование через Web-интерфейс (Сайт)

Веб-приложение полностью автономно и работает прямо в браузере (через HTML5 Canvas API) без обязательного бэкенда:

1. **Мгновенный запуск в браузере**:
   - Просто дважды кликните по файлу [`index.html`](file:///c:/Users/khano/OneDrive/Desktop/VibeCoding/projecct%201/index.html) в проводнике.

2. **Запуск локального сервера**:
   ```bash
   python server.py
   # Или стандартной командой Python:
   python -m http.server 8000
   ```
   Сервер запустится на `http://localhost:8000/index.html` и автоматически откроет страницу в браузере.

3. **Деплой на хостинг**:
   - Файл `index.html` готов к мгновенной публикации на **GitHub Pages**, **Vercel**, **Netlify** или любой статический хостинг.

---

## Использование через CLI

### 1. Mode A — Receipt Archive (Термо-чек)

```bash
# Базовый запуск с дефолтным атмосферным чеком
python main.py photo.jpg -m A -o receipt.png

# С кастомным списком позиций и шириной 580px (58мм)
python main.py photo.jpg -m A -o receipt.png --text "MEMORY FRAGMENT 01\nANALOG TAPE SCAN\nSILVER HALIDE"

# С алгоритмом Atkinson dithering и лентой 800px (80мм)
python main.py photo.jpg -m A -o receipt.png --dither atkinson --width 800
```

### 2. Mode B — Polaroid Snap (Полароидный снимок)

```bash
# Базовый полароид (случайная дата 90-х и классическая подпись)
python main.py portrait.jpg -m B -o polaroid.png

# С точной датой и кастомной подписью на рамке
python main.py portrait.jpg -m B -o polaroid.png --date "1998-04-18" --text "Tigran Solomon's Paper Archive"

# Пропорция кадра 4:5
python main.py portrait.jpg -m B -o polaroid.png --aspect 4:5
```

---

## Использование через Python API

```python
from main import process_image

# 1. Mode A: Receipt Archive
receipt_img = process_image(
    image_path="sample.jpg",
    mode="A",
    custom_text="MEMORY FRAGMENT 01\nANALOG TAPE SCAN",
    custom_date="1998-10-24 16:30:00",
    output_path="receipt_output.png",
    paper_width=580,          # 580 (58мм) или 800 (80мм)
    dither_method="floyd",    # "floyd" или "atkinson"
    apply_torn_edges=True     # Зубчатые перфорированные края
)

# 2. Mode B: Polaroid Snap
polaroid_img = process_image(
    image_path="sample.jpg",
    mode="B",
    custom_text="Tigran Solomon's Paper Archive",
    custom_date="1998-04-18", # Форматируется в '98 04 18 на LCD дисплее
    output_path="polaroid_output.png",
    aspect_ratio="1:1",       # "1:1" или "4:5"
    enable_light_leak=True,   # Случайные оранжево-жёлтые блики
    enable_vignette=True      # Радиальное виньетирование
)
```

---

## Особенности реализации

- **Non-destructive загрузка**: Оригинал исходного файла никогда не перезаписывается, работа ведётся с изолированной копией в памяти.
- **Гистограммное растяжение**: Автоматическая адаптация контраста перед дизерингом сохраняет черты лиц и текстуры читаемыми.
- **Векторный рендер 90s Quartz Date Back**: Аутентичный 7-сегментный LED/LCD экран со скосом, межсегментными зазорами, фоновыми неактивными сегментами и неоновым свечением.
- **Текстура рамки**: Бумажное зерно (5-10% непрозрачности) и внутренний фасеточный шов вокруг фотоокна.
- **Безопасная обработка ошибок**: Понятные сообщения при неверном пути, неподдерживаемом формате или некорректном режиме работы без падения скрипта.
