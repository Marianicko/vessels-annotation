import gradio as gr
from PIL import Image
import os
import time
import traceback
import logging
import sys
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Хранилище оригинальных размеров
original_sizes = {}
MAX_IMAGE_SIZE = 1024

def resize_if_needed(img):
    """Уменьшает изображение для отображения, но запоминает оригинальный размер"""
    if img is None:
        return None
    
    if max(img.size) > MAX_IMAGE_SIZE:
        ratio = MAX_IMAGE_SIZE / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        logger.info(f"Уменьшаем для отображения: {img.size} -> {new_size}")
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    return img

@log_function_call("load_image")
def load_image(img):
    try:
        if img is None:
            return None, None, "Ошибка загрузки", None
        
        # Запоминаем оригинальный размер
        original_size = img.size
        img_id = f"img_{int(time.time())}_{id(img)}"
        original_sizes[img_id] = original_size
        logger.info(f"📸 Загружено изображение: оригинал {original_size}")
        
        # Уменьшаем для отображения
        display_img = resize_if_needed(img)
        logger.info(f"🖥️ Для отображения: {display_img.size}")
        
        editor_state = {
            'background': display_img,
            'layers': [],
            'composite': display_img,
            'img_id': img_id
        }
        
        status_msg = f"Загружено (оригинал {original_size[0]}x{original_size[1]})"
        return display_img, editor_state, status_msg, None
        
    except Exception as e:
        logger.error(f"load_image: ошибка {e}")
        return None, None, f"Ошибка: {str(e)}", None

@log_function_call("save_mask")
def save_mask(display_img, editor_result):
    try:
        if display_img is None:
            return None, "Сначала загрузите изображение!"
        
        # Получаем ID и оригинальный размер
        img_id = editor_result.get('img_id', None) if editor_result else None
        original_size = original_sizes.get(img_id, display_img.size)
        logger.info(f"🔍 ID изображения: {img_id}")
        logger.info(f"📐 Оригинальный размер: {original_size}")
        logger.info(f"📏 Текущий размер: {display_img.size}")
        
        # Создаем маску в текущем размере
        if editor_result is None:
            small_mask = Image.new('L', display_img.size, 0)
            logger.info("Создана пустая маска")
        else:
            layers = editor_result.get('layers', [])
            logger.info(f"Слоев найдено: {len(layers)}")
            
            if layers and len(layers) > 0:
                sketch_layer = layers[0]
                logger.info(f"Слой: режим {sketch_layer.mode}, размер {sketch_layer.size}")
                
                if sketch_layer.mode == 'RGBA':
                    gray = sketch_layer.convert('L')
                    small_mask = gray.point(lambda p: 255 if p > 20 else 0)
                else:
                    small_mask = sketch_layer.convert('L')
                logger.info("Маска создана из слоя")
            else:
                small_mask = Image.new('L', display_img.size, 0)
                logger.info("Создана пустая маска (нет слоев)")
        
        # Восстанавливаем оригинальный размер
        if small_mask.size != original_size:
            logger.info(f"🔄 Увеличиваем маску: {small_mask.size} -> {original_size}")
            final_mask = small_mask.resize(original_size, Image.Resampling.NEAREST)
        else:
            logger.info("Размер маски совпадает с оригиналом")
            final_mask = small_mask
        
        # Сохраняем
        temp_dir = '/tmp'
        os.makedirs(temp_dir, exist_ok=True)
        output_path = os.path.join(temp_dir, f"mask_{int(time.time())}.png")
        
        final_mask.save(output_path)
        file_size = os.path.getsize(output_path)
        logger.info(f"💾 Маска сохранена: {output_path} ({file_size} байт)")
        logger.info(f"✅ Итоговый размер маски: {final_mask.size}")
        
        return output_path, f"Маска сохранена ({final_mask.size[0]}x{final_mask.size[1]})"
        
    except Exception as e:
        logger.error(f"save_mask: ошибка {e}")
        logger.error(traceback.format_exc())
        return None, f"Ошибка: {str(e)}"

# Остальные функции (clear_sketch, reset_all) без изменений
@log_function_call("clear_sketch")
def clear_sketch(image_input, current_editor_state):
    if image_input is None:
        return None, "Нет изображения", None
    
    # Сохраняем img_id при очистке
    img_id = current_editor_state.get('img_id', None) if current_editor_state else None
    
    new_editor_state = {
        'background': image_input,
        'layers': [],
        'composite': image_input,
        'img_id': img_id
    }
    return new_editor_state, "Разметка очищена", None

@log_function_call("reset_all")
def reset_all():
    return None, None, "Готов к работе", None, None

# Создание интерфейса (без изменений)
with gr.Blocks(title="Инструмент бинарной разметки") as demo:
    gr.Markdown("# Инструмент для бинарной разметки")
    gr.Markdown("""
    ### Инструкция:
    1. **Загрузите изображение** (автоматически уменьшается для удобства)
    2. **Обведите ROI** белым цветом. Можно настраивать прозрачность кисти
    3. **Нажмите "Сохранить маску"**. Не забудьте скачать маску после того, как файл будет подготовлен!
    """)
    
    with gr.Row():
        with gr.Column(scale=1):
            image_input = gr.Image(type="pil", label="Исходное изображение")
            load_btn = gr.Button("📤 Загрузить", variant="primary")
        with gr.Column(scale=2):
            status = gr.Textbox(label="Статус", value="Ожидание...")
    
    with gr.Row():
        mask_draw = gr.ImageEditor(
            type="pil",
            label="🖌️ Редактор",
            brush=gr.Brush(colors=["#FFFFFF"], default_size="15"),
            interactive=True,
            height=700
        )
    
    with gr.Row():
        clear_btn = gr.Button("🗑️ Очистить", variant="secondary")
        save_btn = gr.Button("💾 Сохранить", variant="primary")
        reset_btn = gr.Button("🔄 Новое", variant="secondary")
    
    with gr.Row():
        output_file = gr.File(label="📁 Маска")
        mask_preview = gr.Image(label="👁️ Предпросмотр")
    
    # Логика кнопок
    load_btn.click(
        fn=load_image,
        inputs=image_input,
        outputs=[image_input, mask_draw, status, output_file]
    )
    
    clear_btn.click(
        fn=clear_sketch,
        inputs=[image_input, mask_draw],
        outputs=[mask_draw, status, output_file]
    )
    
    reset_btn.click(
        fn=reset_all,
        inputs=None,
        outputs=[image_input, mask_draw, status, output_file, mask_preview]
    )
    
    save_result = save_btn.click(
        fn=save_mask,
        inputs=[image_input, mask_draw],
        outputs=[output_file, status]
    )
    
    save_result.then(
        fn=lambda path: Image.open(path) if path and os.path.exists(path) else None,
        inputs=output_file,
        outputs=[mask_preview]
    )

if __name__ == "__main__":
    demo.queue(default_concurrency_limit=5)
    demo.launch(server_name="0.0.0.0", server_port=7860)
