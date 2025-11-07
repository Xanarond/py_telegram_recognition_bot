import asyncio
import os
import tempfile
import hashlib
from typing import Dict, Optional, List
from datetime import datetime
from pathlib import Path
import shutil

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from config import (
    TEMP_DIR, LOG_LEVEL
)
from utils.logger import setup_logger

logger = setup_logger(__name__)


class TTSGenerator:
    """Агент для генерации speech из text"""
    
    def __init__(self):
        self.temp_dir = Path(TEMP_DIR)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Настройки TTS
        self.default_language = 'ru'
        self.default_speed = 150
        self.supported_languages = ['ru', 'en', 'es', 'fr', 'de', 'it']
        
        # Проверяем доступные TTS движки
        self.available_engines = self._check_available_engines()
        logger.info(f"✅ Доступные TTS движки: {', '.join(self.available_engines)}")
    
    def _check_available_engines(self) -> List[str]:
        """Проверяет доступные TTS движки"""
        engines = []
        
        if PYTTSX3_AVAILABLE:
            try:
                engine = pyttsx3.init()
                engine.stop()
                engines.append('pyttsx3')
                logger.info("✅ pyttsx3 движок доступен")
            except Exception as e:
                logger.warning(f"⚠️ pyttsx3 недоступен: {e}")
        
        if GTTS_AVAILABLE:
            engines.append('gtts')
            logger.info("✅ Google TTS движок доступен")
        
        if not engines:
            logger.warning("⚠️ Ни один TTS движок не доступен")
            
        return engines
    
    async def text_to_speech(self, text: str, options: Dict = None) -> Dict:
        """Основной метод генерации речи из текста"""
        try:
            if not text or not text.strip():
                return self._get_error_result("Пустой текст для озвучивания")
            
            # Настройки по умолчанию
            options = options or {}
            language = options.get('language', self.default_language)
            engine = options.get('engine', self._get_preferred_engine())
            speed = options.get('speed', self.default_speed)
            voice_gender = options.get('voice_gender', 'female')
            
            # Проверяем доступность движка
            if engine not in self.available_engines:
                engine = self._get_preferred_engine()
                
            if not engine:
                return self._get_error_result("Ни один TTS движок не доступен")
            
            # Подготавливаем текст
            prepared_text = self._prepare_text(text)
            
            # Генерируем уникальное имя файла
            filename = self._generate_filename(prepared_text, language, engine, options.get('summary_type'))
            output_path = self.temp_dir / filename
            
            # Генерируем аудио
            if engine == 'gtts':
                result = await self._generate_with_gtts(prepared_text, language, output_path)
            elif engine == 'pyttsx3':
                result = await self._generate_with_pyttsx3(prepared_text, language, speed, voice_gender, output_path)
            else:
                return self._get_error_result(f"Неподдерживаемый движок: {engine}")
            
            if result['success']:
                # Добавляем метаданные
                result.update({
                    'original_text_length': len(text),
                    'processed_text_length': len(prepared_text),
                    'language': language,
                    'engine': engine,
                    'file_size': output_path.stat().st_size if output_path.exists() else 0,
                    'created_at': datetime.now().isoformat(),
                    'agent_version': '1.0'
                })
                
                logger.info(f"✅ Аудио сгенерировано: {filename}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации TTS: {e}")
            return self._get_error_result(f"Техническая ошибка: {str(e)}")
    
    async def _generate_with_gtts(self, text: str, language: str, output_path: Path) -> Dict:
        """Генерация с помощью Google TTS"""
        try:
            # Ограничиваем длину текста для Google TTS
            if len(text) > 5000:
                text = text[:4997] + "..."
            
            loop = asyncio.get_event_loop()
            
            def generate_gtts():
                tts = gTTS(text=text, lang=language, slow=False)
                tts.save(str(output_path))
            
            await loop.run_in_executor(None, generate_gtts)
            
            if output_path.exists():
                return {
                    'success': True,
                    'file_path': str(output_path),
                    'filename': output_path.name,
                    'engine_used': 'gtts',
                    'estimated_duration_seconds': self._estimate_duration(text),
                    'audio_format': 'mp3'
                }
            else:
                return self._get_error_result("Не удалось создать аудиофайл с Google TTS")
                
        except Exception as e:
            logger.error(f"❌ Ошибка Google TTS: {e}")
            return self._get_error_result(f"Google TTS ошибка: {str(e)}")
    
    async def _generate_with_pyttsx3(self, text: str, language: str, speed: int, voice_gender: str, output_path: Path) -> Dict:
        """Генерация с помощью pyttsx3"""
        try:
            loop = asyncio.get_event_loop()
            
            def generate_pyttsx3():
                engine = pyttsx3.init()
                
                # Настройка скорости
                engine.setProperty('rate', speed)
                
                # Выбор голоса
                voices = engine.getProperty('voices')
                if voices:
                    # Пытаемся найти голос по предпочтениям
                    selected_voice = None
                    for voice in voices:
                        voice_name = voice.name.lower()
                        voice_id = voice.id.lower()
                        
                        # Ищем русский голос
                        if language == 'ru' and ('russian' in voice_name or 'ru' in voice_id):
                            selected_voice = voice.id
                            break
                        # Ищем женский/мужской голос
                        elif voice_gender == 'female' and ('female' in voice_name or 'woman' in voice_name):
                            selected_voice = voice.id
                            break
                        elif voice_gender == 'male' and ('male' in voice_name or 'man' in voice_name):
                            selected_voice = voice.id
                            break
                    
                    if selected_voice:
                        engine.setProperty('voice', selected_voice)
                
                # Сохраняем в файл
                engine.save_to_file(text, str(output_path))
                engine.runAndWait()
                engine.stop()
            
            await loop.run_in_executor(None, generate_pyttsx3)
            
            if output_path.exists():
                return {
                    'success': True,
                    'file_path': str(output_path),
                    'filename': output_path.name,
                    'engine_used': 'pyttsx3',
                    'estimated_duration_seconds': self._estimate_duration(text),
                    'audio_format': 'wav'
                }
            else:
                return self._get_error_result("Не удалось создать аудиофайл с pyttsx3")
                
        except Exception as e:
            logger.error(f"❌ Ошибка pyttsx3: {e}")
            return self._get_error_result(f"pyttsx3 ошибка: {str(e)}")
    
    def _prepare_text(self, text: str) -> str:
        """Подготавливает текст для TTS"""
        # Удаляем markdown разметку
        text = text.replace('**', '').replace('*', '').replace('`', '')
        text = text.replace('__', '').replace('_', '')
        
        # Заменяем спецсимволы на читаемые варианты
        replacements = {
            '&': ' и ',
            '@': ' собака ',
            '#': ' хештег ',
            '$': ' доллар ',
            '%': ' процент ',
            '^': ' степень ',
            '+': ' плюс ',
            '=': ' равно ',
            '<': ' меньше ',
            '>': ' больше ',
            '|': ' или ',
            '\\': ' обратный слеш ',
            '/': ' слеш ',
            '🔧': ' технический контент ',
            '📺': ' видео ',
            '💻': ' программирование ',
            '📝': ' статья ',
            '🔬': ' научный контент ',
            '❓': ' вопрос ответ '
        }
        
        for symbol, replacement in replacements.items():
            text = text.replace(symbol, replacement)
        
        # Убираем лишние пробелы
        text = ' '.join(text.split())
        
        return text
    
    def _generate_filename(self, text: str, language: str, engine: str, summary_type: Optional[str] = None) -> str:
        """Генерирует уникальное имя файла"""
        # Создаем хеш от текста
        text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        extension = 'mp3' if engine == 'gtts' else 'wav'
        if summary_type:
            filename = f"tts_{language}_{engine}_{timestamp}_{text_hash}_{summary_type}.{extension}"
        else:
            filename = f"tts_{language}_{engine}_{timestamp}_{text_hash}.{extension}"
        return filename
    
    def _estimate_duration(self, text: str) -> int:
        """Оценивает длительность аудио в секундах"""
        # Примерно 150 слов в минуту для русского языка
        words = len(text.split())
        return max(int(words / 150 * 60), 1)
    
    def _get_preferred_engine(self) -> Optional[str]:
        """Возвращает предпочтительный TTS движок"""
        if 'gtts' in self.available_engines:
            return 'gtts'  # Google TTS обычно лучше качество
        elif 'pyttsx3' in self.available_engines:
            return 'pyttsx3'
        return None
    
    def _get_error_result(self, error_message: str) -> Dict:
        """Возвращает результат с ошибкой"""
        return {
            'success': False,
            'error': error_message,
            'file_path': None,
            'filename': None,
            'engine_used': None,
            'estimated_duration_seconds': 0,
            'audio_format': None,
            'created_at': datetime.now().isoformat(),
            'agent_version': '1.0'
        }
    
    async def create_summary_audio(self, summary_data: Dict, audio_options: Dict = None) -> Dict:
        """Создает аудио из пересказа"""
        try:
            # Извлекаем текст для озвучивания
            if 'brief_summary' in summary_data:
                # Краткий пересказ
                text_parts = [
                    f"Краткий пересказ. {summary_data.get('brief_summary', '')}",
                    f"Главная идея: {summary_data.get('main_thesis', '')}",
                ]
                
                # Добавляем ключевые факты
                key_facts = summary_data.get('key_facts', [])
                if key_facts:
                    text_parts.append("Ключевые факты:")
                    for i, fact in enumerate(key_facts[:3], 1):
                        text_parts.append(f"{i}. {fact}")
                
                # Добавляем выводы
                conclusions = summary_data.get('conclusions', [])
                if conclusions:
                    text_parts.append("Выводы:")
                    for conclusion in conclusions[:2]:
                        text_parts.append(conclusion)
                
                full_text = ". ".join(text_parts)
                
            elif 'executive_summary' in summary_data:
                # Подробный пересказ
                text_parts = [
                    f"Подробный пересказ. {summary_data.get('executive_summary', '')}",
                ]
                
                # Добавляем введение если есть
                introduction = summary_data.get('introduction', '')
                if introduction:
                    text_parts.append(f"Введение: {introduction}")
                
                # Добавляем основные разделы
                main_sections = summary_data.get('main_sections', [])
                if main_sections:
                    text_parts.append("Основные разделы:")
                    for i, section in enumerate(main_sections[:4], 1):  # Увеличиваем до 4 разделов
                        title = section.get('section_title', '')
                        content = section.get('content', '')
                        if title and content:
                            text_parts.append(f"{i}. {title}. {content}")
                
                # Добавляем ключевые выводы
                key_takeaways = summary_data.get('key_takeaways', [])
                if key_takeaways:
                    text_parts.append("Ключевые выводы:")
                    for takeaway in key_takeaways[:3]:
                        text_parts.append(takeaway)
                
                # Добавляем заключение
                conclusion = summary_data.get('conclusion', '')
                if conclusion:
                    text_parts.append(f"Заключение: {conclusion}")
                
                # Добавляем практическую ценность
                practical_value = summary_data.get('practical_value', '')
                if practical_value:
                    text_parts.append(f"Практическая ценность: {practical_value}")
                
                full_text = ". ".join(text_parts)
            else:
                return self._get_error_result("Не найден подходящий текст для озвучивания")
            
            # Ограничиваем длину
            if len(full_text) > 3000:
                full_text = full_text[:2997] + "..."
            
            # Генерируем аудио
            audio_options = audio_options or {}
            
            # Добавляем тип пересказа в опции для создания уникального имени файла
            summary_type = 'brief' if 'brief_summary' in summary_data else 'detailed'
            audio_options['summary_type'] = summary_type
            
            result = await self.text_to_speech(full_text, audio_options)
            
            # Добавляем информацию о пересказе
            if result['success']:
                result.update({
                    'content_type': 'summary',
                    'summary_type': summary_type,
                    'source_url': summary_data.get('source_url', ''),
                    'original_summary_length': len(summary_data.get('brief_summary', summary_data.get('executive_summary', ''))),
                })
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания аудио пересказа: {e}")
            return self._get_error_result(f"Ошибка создания аудио: {str(e)}")
    
    async def get_audio_info(self, file_path: str) -> Dict:
        """Получает информацию об аудиофайле"""
        try:
            path = Path(file_path)
            if not path.exists():
                return {'exists': False}
            
            stat = path.stat()
            return {
                'exists': True,
                'size_bytes': stat.st_size,
                'size_mb': round(stat.st_size / 1024 / 1024, 2),
                'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'extension': path.suffix,
                'filename': path.name
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения информации об аудио: {e}")
            return {'exists': False, 'error': str(e)}
    
    def cleanup_old_files(self, max_age_hours: int = 24) -> int:
        """Очищает старые временные аудиофайлы"""
        try:
            current_time = datetime.now().timestamp()
            max_age_seconds = max_age_hours * 3600
            cleaned_count = 0
            
            for file_path in self.temp_dir.glob("tts_*.mp3"):
                try:
                    if file_path.is_file():
                        file_age = current_time - file_path.stat().st_mtime
                        if file_age > max_age_seconds:
                            file_path.unlink()
                            cleaned_count += 1
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось удалить {file_path}: {e}")
            
            for file_path in self.temp_dir.glob("tts_*.wav"):
                try:
                    if file_path.is_file():
                        file_age = current_time - file_path.stat().st_mtime
                        if file_age > max_age_seconds:
                            file_path.unlink()
                            cleaned_count += 1
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось удалить {file_path}: {e}")
            
            if cleaned_count > 0:
                logger.info(f"✅ Очищено старых аудиофайлов: {cleaned_count}")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"❌ Ошибка очистки старых файлов: {e}")
            return 0 