import os
from datetime import datetime
from typing import Dict

from config import TEMP_DIR, FONT_PATHS
from utils.logger import setup_logger

logger = setup_logger(__name__)

# PDF библиотеки - используем только ReportLab
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


class PDFGenerator:
    @staticmethod
    def create_html_table(sources: list, sort_by: str = 'timestamp', sort_order: str = 'desc') -> str:
        """Создает HTML таблицу с источниками
        
        Args:
            sources (list): Список источников
            sort_by (str): Поле для сортировки
            sort_order (str): Порядок сортировки ('asc' или 'desc')
        """
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
            <style>
                @font-face {
                    font-family: 'DejaVu Sans';
                    src: local('DejaVu Sans');
                }
                body {
                    font-family: 'DejaVu Sans', Arial, sans-serif;
                    margin: 5px;
                }
                h1 {
                    color: #1f4e79;
                    text-align: center;
                    margin-bottom: 30px;
                }
                .info {
                    text-align: center;
                    margin-bottom: 20px;
                    color: #666;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 30px;
                    font-size: 10px;
                }
                th {
                    background-color: #1f4e79;
                    color: white;
                    padding: 8px 4px;
                    text-align: center;
                    border: 1px solid #ddd;
                }
                td {
                    padding: 6px 4px;
                    text-align: center;
                    border: 1px solid #ddd;
                    word-wrap: break-word;
                }
                tr:nth-child(even) {
                    background-color: #f9f9f9;
                }
                tr:nth-child(odd) {
                    background-color: white;
                }
                .priority-high { color: #d63384; font-weight: bold; }
                .priority-medium { color: #fd7e14; }
                .priority-low { color: #198754; }
                .status-read { color: #198754; font-weight: bold; }
                .status-unread { color: #6c757d; }
                @page {
                    size: A4 landscape;
                    margin: 1cm;
                }
            </style>
        </head>
        <body>
        """
        
        # Заголовок
        html += f"""
            <h1>📚 ТАБЛИЦА ИСТОЧНИКОВ</h1>
            <div class="info">
                Всего источников: {len(sources)} | 
                Дата создания: {datetime.now().strftime('%d.%m.%Y %H:%M')}
            </div>
        """
        
        # Таблица
        html += """
            <table>
                <thead>
                    <tr>
                        <th style="width: 3%;">№</th>
                        <th style="width: 18%;">Название</th>
                        <th style="width: 8%;">Сайт</th>
                        <th style="width: 8%;">Категория</th>
                        <th style="width: 8%;">Статус</th>
                        <th style="width: 6%;">Релевантность</th>
                        <th style="width: 8%;">Приоритет</th>
                        <th style="width: 6%;">Время чтения</th>
                        <th style="width: 8%;">Дата</th>
                        <th style="width: 13%;">Теги</th>
                        <th style="width: 14%;">Ссылка</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        # Источники уже должны быть отсортированы до вызова этой функции
        for i, source in enumerate(sources, 1):
            # Обрабатываем дату - проверяем как timestamp, так и created_at
            date_str = 'Неизвестно'
            try:
                # Сначала пробуем timestamp (из старой системы)
                if source.get('timestamp'):
                    timestamp = datetime.fromisoformat(source.get('timestamp'))
                    date_str = timestamp.strftime('%d.%m.%Y')
                # Если нет timestamp, пробуем created_at (из MongoDB)
                elif source.get('created_at'):
                    created_at = source.get('created_at')
                    if isinstance(created_at, datetime):
                        date_str = created_at.strftime('%d.%m.%Y')
                    else:
                        # Если это строка, пробуем парсить
                        timestamp = datetime.fromisoformat(str(created_at))
                        date_str = timestamp.strftime('%d.%m.%Y')
            except Exception as e:
                logger.debug(f"Не удалось обработать дату для HTML источника {i}: {e}")
                date_str = 'Неизвестно'
            
            # Получаем данные
            title = source.get('title', 'Без названия')
            if len(title) > 40:
                title = title[:37] + '...'
            
            url = source.get('url', '')
            try:
                domain = url.split('/')[2] if '/' in url else 'unknown'
            except:
                domain = 'unknown'
            
            category = source.get('category', 'unknown')
            relevance = source.get('relevance_score', '?')
            priority = source.get('priority_level', 'medium')
            reading_time = source.get('estimated_reading_time', '?')
            
            # Теги
            tags = source.get('tags', [])[:4]
            tags_str = ', '.join(tags) if tags else '-'
            
            
            # Класс для приоритета
            priority_class = f"priority-{priority}"
            priority_text = {'high': 'Высокий', 'medium': 'Средний', 'low': 'Низкий'}.get(priority, 'Средний')
            
            # Статус прочтения
            read_status = source.get('read_status', 'unread')
            read_status_text = '✅ Прочитано' if read_status == 'read' else '📖 Не прочитано'
            read_status_class = 'status-read' if read_status == 'read' else 'status-unread'
            
            html += f"""
                <tr>
                    <td>{i}</td>
                    <td style="text-align: left;">{title}</td>
                    <td>{domain}</td>
                    <td>{category}</td>
                    <td class="{read_status_class}">{read_status_text}</td>
                    <td><strong>{relevance}/10</strong></td>
                    <td class="{priority_class}">{priority_text}</td>
                    <td>{reading_time} мин</td>
                    <td>{date_str}</td>
                    <td style="text-align: left; font-size: 8px;">{tags_str}</td>
                    <td style="text-align: left; font-size: 7px; word-break: break-all;">{url}</td>
                </tr>
            """
        
        html += """
                </tbody>
            </table>
        </body>
        </html>
        """
        
        return html

    @staticmethod
    def create_sources_pdf(stats: Dict, user_id: int, sort_by: str = 'created_at', 
                         sort_order: str = 'desc', read_filter: str = 'all',
                         priority_filter: str = 'all', category_filter: str = 'all') -> str:
        """Создает PDF с таблицей источников и возвращает путь к файлу
        
        Args:
            stats (Dict): Статистика пользователя
            user_id (int): ID пользователя
            sort_by (str): Поле для сортировки ('timestamp', 'relevance_score', 'estimated_reading_time', 'priority_level')
            sort_order (str): Порядок сортировки ('asc' или 'desc')
            read_filter (str): Фильтр по статусу прочтения ('all', 'read', 'unread')
            priority_filter (str): Фильтр по приоритету ('all', 'high', 'medium', 'low')
            category_filter (str): Фильтр по категории ('all' или название категории)
        """
        sources = stats.get('sources', [])
        if not sources:
            return None
            
        # Применяем фильтры
        filtered_sources = sources
        
        # Логируем исходные параметры
        logger.info(f"Экспорт PDF с параметрами: sort_by={sort_by}, sort_order={sort_order}, read_filter={read_filter}, priority_filter={priority_filter}")
        logger.info(f"Всего источников до фильтрации: {len(filtered_sources)}")
        
        # Проверяем значения read_status в первых 5 источниках для отладки
        for i, source in enumerate(filtered_sources[:5]):
            logger.info(f"Источник {i}: read_status={source.get('read_status')}, priority_level={source.get('priority_level')}")
        
        # Фильтр по статусу прочтения
        if read_filter != 'all':
            # Проверяем, что read_filter имеет допустимое значение
            if read_filter in ['read', 'unread']:
                filtered_sources = [s for s in filtered_sources if s.get('read_status', 'unread') == read_filter]
                logger.info(f"После фильтра по статусу '{read_filter}': {len(filtered_sources)}")
            else:
                logger.warning(f"Некорректное значение read_filter: {read_filter}")
            
        # Фильтр по приоритету
        if priority_filter != 'all':
            # Проверяем, что priority_filter имеет допустимое значение
            if priority_filter in ['high', 'medium', 'low']:
                filtered_sources = [s for s in filtered_sources if s.get('priority_level', 'medium') == priority_filter]
                logger.info(f"После фильтра по приоритету '{priority_filter}': {len(filtered_sources)}")
            else:
                logger.warning(f"Некорректное значение priority_filter: {priority_filter}")
            
        # Фильтр по категории
        if category_filter != 'all':
            filtered_sources = [s for s in filtered_sources if s.get('category', 'unknown') == category_filter]
            logger.info(f"После фильтра по категории '{category_filter}': {len(filtered_sources)}")
            
        # Если после фильтрации нет источников
        if not filtered_sources:
            logger.warning("После применения всех фильтров не осталось источников")
            return None
            
        # Функция для получения значения для сортировки
        def get_sort_value(source):
            value = source.get(sort_by)
            
            if sort_by in ['timestamp', 'created_at']:
                # Преобразуем дату из разных форматов в datetime для корректной сортировки
                try:
                    # Сначала пробуем created_at (из MongoDB)
                    if source.get('created_at'):
                        created_at = source.get('created_at')
                        if isinstance(created_at, datetime):
                            return created_at
                        else:
                            return datetime.fromisoformat(str(created_at))
                    # Затем пробуем timestamp (из старой системы)
                    elif source.get('timestamp'):
                        return datetime.fromisoformat(source.get('timestamp'))
                    return datetime.min
                except (ValueError, TypeError):
                    return datetime.min
            elif sort_by == 'priority_level':
                # Преобразуем приоритет в числовое значение для сортировки
                priority_values = {'high': 3, 'medium': 2, 'low': 1}
                return priority_values.get(value, 0)
            elif sort_by in ['relevance_score', 'estimated_reading_time']:
                # Преобразуем в число, если не удается - возвращаем 0
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return 0
            return value or ''  # Для остальных полей возвращаем значение или пустую строку
            
        # Сортируем источники
        logger.info(f"Сортировка источников по полю '{sort_by}' в порядке '{sort_order}'")
        filtered_sources.sort(
            key=get_sort_value,
            reverse=(sort_order == 'desc')
        )
        logger.info(f"Сортировка завершена, первые 3 даты: {[s.get('timestamp', '')[:10] for s in filtered_sources[:3]]}")
        
        # Создаем директорию для временных файлов
        os.makedirs(TEMP_DIR, exist_ok=True)
        
        # Формируем читаемое название файла
        current_date = datetime.now().strftime('%d-%m-%Y')
        
        # Добавляем информацию о фильтрах в название
        filter_parts = []
        if read_filter != 'all':
            filter_parts.append('прочитанные' if read_filter == 'read' else 'непрочитанные')
        if priority_filter != 'all':
            priority_names = {'high': 'высокий', 'medium': 'средний', 'low': 'низкий'}
            filter_parts.append(f"приоритет-{priority_names.get(priority_filter, priority_filter)}")
        if category_filter != 'all':
            filter_parts.append(f"категория-{category_filter[:15]}")
            
        filter_suffix = f"_{'-'.join(filter_parts)}" if filter_parts else ""
        
        pdf_filename = f"Анализ-источников{filter_suffix}_{current_date}.pdf"
        pdf_path = os.path.join(TEMP_DIR, pdf_filename)
        
        try:
            # Используем reportlab напрямую
            return PDFGenerator.create_simple_pdf(filtered_sources, pdf_path, user_id, sort_by, sort_order, read_filter, priority_filter, category_filter)
            
        except Exception as e:
            logger.error(f"Ошибка при создании PDF: {e}")
            return PDFGenerator.create_text_file(filtered_sources, user_id, sort_by, sort_order, read_filter, priority_filter, category_filter)

    @staticmethod
    def create_simple_pdf(sources: list, pdf_path: str, user_id: int, 
                         sort_by: str = 'created_at', sort_order: str = 'desc',
                         read_filter: str = 'all', priority_filter: str = 'all',
                         category_filter: str = 'all') -> str:
        """Простая версия PDF с reportlab"""
        try:
            # Регистрируем шрифт DejaVu Sans для поддержки кириллицы
            try:
                font_loaded = False
                for font_path in FONT_PATHS:
                    if os.path.exists(font_path):
                        pdfmetrics.registerFont(TTFont('DejaVu', font_path))
                        default_font = 'DejaVu'
                        font_loaded = True
                        logger.info(f"Загружен шрифт: {font_path}")
                        break
                
                if not font_loaded:
                    logger.warning("Не удалось найти шрифт DejaVu Sans, используем стандартный")
                    default_font = 'Helvetica'
                    
            except Exception as e:
                logger.error(f"Ошибка при загрузке шрифта: {e}")
                default_font = 'Helvetica'
            
            # Создаем документ с правильными отступами
            doc = SimpleDocTemplate(
                pdf_path,
                pagesize=landscape(A4),
                rightMargin=2*mm,
                leftMargin=2*mm,
                topMargin=2*mm,
                bottomMargin=2*mm
            )
            
            # Создаем базовые стили
            styles = getSampleStyleSheet()
            
            # Стиль для заголовка таблицы
            header_style = ParagraphStyle(
                'HeaderStyle',
                parent=styles['Heading1'],
                fontSize=10,
                leading=12,
                fontName=default_font,
                alignment=1,  # По центру
                spaceAfter=2*mm
            )
            
            # Стиль для ячеек таблицы
            cell_style = ParagraphStyle(
                'CellStyle',
                parent=styles['Normal'],
                fontSize=8,
                leading=10,
                fontName=default_font,
                alignment=1  # По центру
            )

            # Стиль для URL без отступов
            url_style = ParagraphStyle(
                'URLStyle',
                parent=styles['Normal'],
                fontSize=7,
                leading=8,
                fontName=default_font,
                alignment=0,  # По левому краю
                leftIndent=0,
                rightIndent=0,
                spaceBefore=0,
                spaceAfter=0
            )
            
            # Подготавливаем данные таблицы
            table_data = []
            
            # Заголовки с правильным форматированием
            headers = [
                Paragraph('<b>#</b>', header_style),
                Paragraph('<b>Название</b>', header_style),
                Paragraph('<b>Источник</b>', header_style),
                Paragraph('<b>Категория</b>', header_style),
                Paragraph('<b>Статус</b>', header_style),
                Paragraph('<b>Оценка</b>', header_style),
                Paragraph('<b>Приоритет</b>', header_style),
                Paragraph('<b>Время</b>', header_style),
                Paragraph('<b>Дата</b>', header_style),
                Paragraph('<b>Теги</b>', header_style),
                Paragraph('<b>Ссылка</b>', header_style)
            ]
            table_data.append(headers)
            
            # Добавляем данные с правильным форматированием (источники уже отсортированы в create_sources_pdf)
            for i, source in enumerate(sources, 1):
                # Обрабатываем дату - проверяем как timestamp, так и created_at
                date_str = 'Неизвестно'
                try:
                    # Сначала пробуем timestamp (из старой системы)
                    if source.get('timestamp'):
                        timestamp = datetime.fromisoformat(source.get('timestamp'))
                        date_str = timestamp.strftime('%d.%m.%Y')
                    # Если нет timestamp, пробуем created_at (из MongoDB)
                    elif source.get('created_at'):
                        created_at = source.get('created_at')
                        if isinstance(created_at, datetime):
                            date_str = created_at.strftime('%d.%m.%Y')
                        else:
                            # Если это строка, пробуем парсить
                            timestamp = datetime.fromisoformat(str(created_at))
                            date_str = timestamp.strftime('%d.%m.%Y')
                except Exception as e:
                    logger.debug(f"Не удалось обработать дату для источника {i}: {e}")
                    date_str = 'Неизвестно'
                
                # Форматируем название и категорию
                title = source.get('title', 'Без названия')
                if len(title) > 40:
                    title = title[:37] + '...'
                
                domain = source.get('url', '').split('/')[2] if '/' in source.get('url', '') else 'unknown'
                category = source.get('category', 'unknown')
                if len(category) > 15:
                    category = category[:12] + '...'
                
                # Теги
                tags = source.get('tags', [])[:3]
                tags_str = ', '.join(tags) if tags else '-'
                
                # URL для отображения
                source_url = source.get('url', '')
                display_url = source_url
                if len(display_url) > 35:
                    display_url = display_url[:32] + '...'
                
                # Форматируем приоритет
                priority_map = {
                    'high': '<font color="red">ВЫСОКИЙ</font>',
                    'medium': '<font color="orange">СРЕДНИЙ</font>',
                    'low': '<font color="green">НИЗКИЙ</font>'
                }
                priority = priority_map.get(source.get('priority_level', 'medium'), 
                                         '<font color="orange">СРЕДНИЙ</font>')
                
                # Форматируем статус прочтения
                read_status = source.get('read_status', 'unread')
                read_status_text = '<font color="green">✅ ПРОЧИТАНО</font>' if read_status == 'read' else '<font color="gray">📖 НЕ ПРОЧИТАНО</font>'
                
                # Создаем строку таблицы с обработкой кириллицы
                try:
                    # Безопасное экранирование HTML и поддержка кириллицы
                    safe_title = title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    safe_domain = domain.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    safe_category = category.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    safe_tags = tags_str.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    safe_url = display_url.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    
                    row = [
                        Paragraph(str(i), cell_style),
                        Paragraph(safe_title, cell_style),
                        Paragraph(safe_domain, cell_style),
                        Paragraph(safe_category, cell_style),
                        Paragraph(read_status_text, cell_style),
                        Paragraph(f"{source.get('relevance_score', '?')}/10", cell_style),
                        Paragraph(priority, cell_style),
                        Paragraph(f"{source.get('estimated_reading_time', '?')} мин", cell_style),
                        Paragraph(date_str, cell_style),
                        Paragraph(safe_tags, cell_style),
                        Paragraph(f'<link href="{source_url}">{safe_url}</link>', url_style)
                    ]
                    table_data.append(row)
                except Exception as row_error:
                    logger.warning(f"Ошибка при обработке строки {i}: {row_error}")
                    # Добавляем базовую строку без сложного форматирования
                    simple_row = [str(i), "Ошибка", domain[:15], category[:10], "?", "средний", "?", date_str, "-", display_url[:20]]
                    table_data.append(simple_row)
            
            # Задаем размеры колонок (в миллиметрах) для 11 колонок
            col_widths = [8*mm, 45*mm, 22*mm, 22*mm, 20*mm, 15*mm, 20*mm, 15*mm, 20*mm, 30*mm, 36*mm]
            
            # Создаем таблицу
            table = Table(table_data, colWidths=col_widths, repeatRows=1)
            
            # Стилизуем таблицу
            table_style = TableStyle([
                # Стили для заголовка
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                
                # Отступы в ячейках
                ('TOPPADDING', (0, 0), (-1, -1), 3*mm),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3*mm),
                ('LEFTPADDING', (0, 0), (-1, -1), 2*mm),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2*mm),
                
                # Специальные отступы для колонки с URL (последняя колонка)
                ('TOPPADDING', (-1, 1), (-1, -1), 0),
                ('BOTTOMPADDING', (-1, 1), (-1, -1), 0),
                ('LEFTPADDING', (-1, 1), (-1, -1), 1*mm),
                ('RIGHTPADDING', (-1, 1), (-1, -1), 1*mm),
                
                # Границы
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                
                # Чередующиеся цвета строк
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')])
            ])
            
            # Применяем стили
            table.setStyle(table_style)
            
            # Создаем элементы документа
            elements = []
            
            # Добавляем заголовок
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=14,
                fontName=default_font,
                alignment=1,
                spaceAfter=5*mm
            )
            
            # Формируем информацию о фильтрах
            filter_info = []
            if read_filter != 'all':
                filter_info.append(f"Статус: {'Прочитанные' if read_filter == 'read' else 'Непрочитанные'}")
            if priority_filter != 'all':
                priority_names = {'high': 'Высокий', 'medium': 'Средний', 'low': 'Низкий'}
                filter_info.append(f"Приоритет: {priority_names.get(priority_filter, priority_filter)}")
            if category_filter != 'all':
                filter_info.append(f"Категория: {category_filter}")
                
            # Формируем информацию о сортировке
            sort_field_names = {
                'created_at': 'дате',
                'timestamp': 'дате',  # Для совместимости
                'relevance_score': 'релевантности',
                'estimated_reading_time': 'времени чтения',
                'priority_level': 'приоритету'
            }
            sort_order_names = {'asc': '(по возрастанию)', 'desc': '(по убыванию)'}
            sort_info = f"Сортировка по {sort_field_names.get(sort_by, sort_by)} {sort_order_names.get(sort_order, '')}"
            
            # Формируем заголовок
            title_text = f'<b>Таблица источников (всего: {len(sources)})</b>'
            if filter_info:
                title_text += f'<br/><font size="10">Фильтры: {" | ".join(filter_info)}</font>'
            title_text += f'<br/><font size="10">{sort_info}</font>'
            
            title = Paragraph(title_text, title_style)
            elements.append(title)
            
            # Добавляем дату создания
            date_style = ParagraphStyle(
                'DateInfo',
                parent=styles['Normal'],
                fontSize=8,
                fontName=default_font,
                alignment=1,
                spaceAfter=10*mm
            )
            date_info = Paragraph(
                f'Дата создания: {datetime.now().strftime("%d.%m.%Y %H:%M")}',
                date_style
            )
            elements.append(date_info)
            
            # Добавляем таблицу
            elements.append(table)
            
            # Собираем документ
            doc.build(elements)
            
            # Проверяем, что PDF файл создан и не пустой
            if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 1024:  # Минимум 1KB
                logger.info(f"PDF успешно создан: {pdf_path} ({os.path.getsize(pdf_path)} байт)")
                return pdf_path
            else:
                logger.error(f"PDF файл не создан или слишком мал: {pdf_path}")
                return PDFGenerator.create_text_file(sources, user_id, sort_by, sort_order, read_filter, priority_filter, category_filter)
            
        except Exception as e:
            logger.error(f"Ошибка при создании простого PDF: {e}")
            return PDFGenerator.create_text_file(sources, user_id, sort_by, sort_order, read_filter, priority_filter, category_filter)

    @staticmethod
    def create_text_file(sources: list, user_id: int, sort_by: str = 'created_at',
                        sort_order: str = 'desc', read_filter: str = 'all',
                        priority_filter: str = 'all', category_filter: str = 'all') -> str:
        """Создает текстовый файл как fallback"""
        try:
            # Создаем директорию для временных файлов
            os.makedirs(TEMP_DIR, exist_ok=True)
            
            current_date = datetime.now().strftime('%d-%m-%Y')
            
            # Добавляем информацию о фильтрах в название
            filter_parts = []
            if read_filter != 'all':
                filter_parts.append('прочитанные' if read_filter == 'read' else 'непрочитанные')
            if priority_filter != 'all':
                priority_names = {'high': 'высокий', 'medium': 'средний', 'low': 'низкий'}
                filter_parts.append(f"приоритет-{priority_names.get(priority_filter, priority_filter)}")
            if category_filter != 'all':
                filter_parts.append(f"категория-{category_filter[:15]}")
                
            filter_suffix = f"_{'-'.join(filter_parts)}" if filter_parts else ""
            
            txt_filename = f"Анализ-источников{filter_suffix}_{current_date}.txt"
            txt_path = os.path.join(TEMP_DIR, txt_filename)
            
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write("📚 ТАБЛИЦА ИСТОЧНИКОВ\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"Всего источников: {len(sources)}\n")
                f.write(f"Дата создания: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n")
                
                # Добавляем информацию о фильтрах
                if read_filter != 'all' or priority_filter != 'all' or category_filter != 'all':
                    f.write("ПРИМЕНЁННЫЕ ФИЛЬТРЫ:\n")
                    if read_filter != 'all':
                        f.write(f"• Статус: {'Прочитанные' if read_filter == 'read' else 'Непрочитанные'}\n")
                    if priority_filter != 'all':
                        priority_names = {'high': 'Высокий', 'medium': 'Средний', 'low': 'Низкий'}
                        f.write(f"• Приоритет: {priority_names.get(priority_filter, priority_filter)}\n")
                    if category_filter != 'all':
                        f.write(f"• Категория: {category_filter}\n")
                    f.write("\n")
                
                # Добавляем информацию о сортировке
                sort_field_names = {
                    'created_at': 'дате',
                    'timestamp': 'дате',  # Для совместимости
                    'relevance_score': 'релевантности',
                    'estimated_reading_time': 'времени чтения',
                    'priority_level': 'приоритету'
                }
                sort_order_names = {'asc': '(по возрастанию)', 'desc': '(по убыванию)'}
                f.write(f"Сортировка по {sort_field_names.get(sort_by, sort_by)} {sort_order_names.get(sort_order, '')}\n\n")
                f.write("=" * 50 + "\n\n")
                
                for i, source in enumerate(sources, 1):
                    # Обрабатываем дату - проверяем как timestamp, так и created_at
                    date_str = 'Неизвестно'
                    try:
                        # Сначала пробуем timestamp (из старой системы)
                        if source.get('timestamp'):
                            timestamp = datetime.fromisoformat(source.get('timestamp'))
                            date_str = timestamp.strftime('%d.%m.%Y')
                        # Если нет timestamp, пробуем created_at (из MongoDB)
                        elif source.get('created_at'):
                            created_at = source.get('created_at')
                            if isinstance(created_at, datetime):
                                date_str = created_at.strftime('%d.%m.%Y')
                            else:
                                # Если это строка, пробуем парсить
                                timestamp = datetime.fromisoformat(str(created_at))
                                date_str = timestamp.strftime('%d.%m.%Y')
                    except Exception as e:
                        logger.debug(f"Не удалось обработать дату для источника {i}: {e}")
                        date_str = 'Неизвестно'
                    
                    f.write(f"{i}. {source.get('title', 'Без названия')}\n")
                    f.write(f"   URL: {source.get('url', 'URL не указан')}\n")
                    f.write(f"   Категория: {source.get('category', 'unknown')}\n")
                    f.write(f"   Статус: {'✅ Прочитано' if source.get('read_status') == 'read' else '📖 Не прочитано'}\n")
                    f.write(f"   Релевантность: {source.get('relevance_score', '?')}/10\n")
                    f.write(f"   Приоритет: {source.get('priority_level', 'medium')}\n")
                    f.write(f"   Дата: {date_str}\n")
                    f.write(f"   Теги: {', '.join(source.get('tags', []))}\n\n")
            
            return txt_path
            
        except Exception as e:
            logger.error(f"Ошибка при создании текстового файла: {e}")
            return None 