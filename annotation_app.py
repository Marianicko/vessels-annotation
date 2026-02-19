import gradio as gr
from PIL import Image, ImageDraw
import numpy as np
import os
import time

# Функция для сохранения маски
def save_mask(original_img, editor_result):
    """
    Сохраняет маску (слой рисования) как отдельное PNG изображение.
    Маска должна быть бинарной: фон - 0, ROI - 255.
    """
    if original_img is None:
        return None, "Сначала загрузите изображение!"
    
    # Используем timestamp для уникальности, если не можем получить имя файла
    file_name = f"image_{int(time.time())}"
    
    # Пытаемся получить имя файла (но Gradio часто не дает)
    if hasattr(original_img, 'filename') and original_img.filename:
        # Извлекаем имя файла без расширения
        base_name = os.path.basename(original_img.filename)
        # Убираем временные префиксы Gradio
        if 'tmp' not in base_name.lower():
            file_name = os.path.splitext(base_name)[0]
            print(f"Нашли имя: {file_name}")
    
    # editor_result - это словарь от ImageEditor
    if editor_result is None:
        # Если разметки нет, создаем пустую маску
        mask = Image.new('L', original_img.size, 0)
    else:
        # Получаем слои рисования
        layers = editor_result.get('layers', [])
        
        if layers and len(layers) > 0:
            # Берем первый слой с разметкой
            sketch_layer = layers[0]
            
            # Конвертируем в маску
            if sketch_layer.mode == 'RGBA':
                # Превращаем в grayscale
                gray = sketch_layer.convert('L')
                # Любой непрозрачный пиксель (>0) считаем ROI
                mask = gray.point(lambda p: 255 if p > 20 else 0)
            else:
                mask = sketch_layer.convert('L')
        else:
            # Если слоев нет, создаем пустую маску
            mask = Image.new('L', original_img.size, 0)
    
    # Формируем имя файла в формате {original_name}_mask.png
    output_path = f"{file_name}_mask.png"
    
    # Проверяем, не существует ли уже файл, и если да - добавляем номер
    counter = 1
    while os.path.exists(output_path):
        output_path = f"{file_name}_mask_{counter}.png"
        counter += 1
    
    mask.save(output_path)
    return output_path, f"Маска сохранена как {output_path}"

# Функция для очистки разметки (НОВЫЙ ВАРИАНТ - сохраняет изображение)
def clear_sketch(image_input, current_editor_state):
    """
    Очищает только разметку, оставляя изображение
    """
    if image_input is None:
        return None, "Нет изображения для разметки", None
    
    # Создаем новый пустой редактор с тем же фоновым изображением
    new_editor_state = {
        'background': image_input,
        'layers': [],  # Пустые слои
        'composite': image_input  # Только фон, без разметки
    }
    
    return new_editor_state, "Разметка очищена", None

# Функция для полного сброса (НОВЫЙ ВАРИАНТ - очищает всё)
def reset_all():
    """
    Полностью сбрасывает приложение - и изображение, и разметку
    """
    return None, None, "Готов к работе. Загрузите изображение.", None, None

# Функция обновления интерфейса при загрузке картинки
def load_image(img):
    if img is None:
        return None, None, "Ошибка загрузки", None
    
    # Формируем информационное сообщение
    if hasattr(img, 'filename') and img.filename:
        base_name = os.path.basename(img.filename)
        # Убираем временные префиксы для отображения
        display_name = base_name
        if 'tmp' in base_name.lower():
            display_name = "изображение (временный файл)"
        file_info = f"Загружено: {display_name}"
    else:
        file_info = f"Изображение загружено: {img.size[0]}x{img.size[1]}"
    
    # Создаем словарь для ImageEditor с правильной структурой
    editor_state = {
        'background': img,
        'layers': [],  # Пустой слой для рисования
        'composite': img
    }
    
    return img, editor_state, file_info, None

# Собираем интерфейс Gradio
with gr.Blocks(title="Инструмент бинарной разметки", theme=gr.themes.Citrus()) as demo:
    gr.Markdown("# Инструмент для бинарной разметки")
    gr.Markdown("""
    ### Инструкция:
    1. **Загрузите изображение**: клик на первое окно, затем нажать кнопку "Загрузить изображение". В поле "статус" должно появиться сообщение об успешной загрузке
    2. **Обведите ROI** (область интереса) белым цветом с помощью кисти. Для изменения размера кисти можно использовать колёсико мыши. Можно закрашивать сосуды, можно только обводить контур - как удобнее :) 
    3. **Нажмите "Сохранить маску"** для получения бинарного изображения. Не забудьте его скачать
    """)
    
    with gr.Row():
        with gr.Column(scale=1):
            # Кнопка загрузки
            image_input = gr.Image(type="pil", label="Исходное изображение")
            load_btn = gr.Button("📤 Загрузить изображение", variant="primary")
            
        with gr.Column(scale=2):
            # Статус
            status = gr.Textbox(label="Статус", value="Ожидание загрузки...", interactive=False)
    
    with gr.Row():
        with gr.Column():
            # Окно для разметки
            mask_draw = gr.ImageEditor(
                type="pil",
                label="🖌️ Редактор разметки (рисуйте белым)",
                brush=gr.Brush(colors=["#FFFFFF"], default_size="15"), # Только белый цвет
                interactive=True,
                height=1000
            )
    
    with gr.Row():
        clear_btn = gr.Button("🗑️ Очистить разметку", variant="secondary")
        save_btn = gr.Button("💾 Сохранить маску", variant="primary")
        reset_btn = gr.Button("🔄 Новое изображение", variant="secondary")
    
    with gr.Row():
        with gr.Column():
            output_file = gr.File(label="📁 Сохраненная маска")
        with gr.Column():
            mask_preview = gr.Image(type="pil", label="👁️ Предпросмотр маски")
    
    # Логика загрузки изображения
    load_btn.click(
        fn=load_image,
        inputs=image_input,
        outputs=[image_input, mask_draw, status, output_file]
    )
    
    # Логика очистки разметки (НОВОЕ - правильно работает)
    clear_btn.click(
        fn=clear_sketch,
        inputs=[image_input, mask_draw],
        outputs=[mask_draw, status, output_file]
    )
    
    # Логика полного сброса (НОВОЕ - правильно работает)
    reset_btn.click(
        fn=reset_all,
        inputs=None,
        outputs=[image_input, mask_draw, status, output_file, mask_preview]
    )
    
    # При сохранении обновляем и статус, и превью
    save_result = save_btn.click(
        fn=save_mask,
        inputs=[image_input, mask_draw],
        outputs=[output_file, status]
    )
    
    # Показываем превью сохраненной маски
    save_result.then(
        fn=lambda mask_path: Image.open(mask_path) if mask_path and os.path.exists(mask_path) else None,
        inputs=output_file,
        outputs=[mask_preview]
    )

if __name__ == "__main__":
    # Для локального запуска
    demo.launch(server_name="0.0.0.0", server_port=7860)

