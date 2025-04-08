import requests
import json
import re
import os
import argparse
from py2neo import Graph, Node, Relationship, NodeMatcher, RelationshipMatcher
import time
from dotenv import load_dotenv
from course_format_detector import get_course_format
from extract_concepts import extract_course_concepts

# Загрузка переменных окружения
load_dotenv()

# Конфигурация из переменных окружения
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
COURSE_FILE = os.getenv("COURSE_FILE", "course.txt")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j")
AI_MODEL = os.getenv("AI_MODEL", "x-ai/grok-2-1212")

# Проверка наличия необходимых переменных
if not OPENROUTER_API_KEY:
    raise ValueError("Отсутствует OPENROUTER_API_KEY. Проверьте файл .env")

# Функция для чтения текста курса
def read_course_file(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()

# Функция для разделения текста на главы
def split_into_chapters(text):
    # Ищем главы по шаблону "Глава X. Название главы"
    chapter_pattern = r"Глава \d+\.\s+([^\n]+)"
    chapter_titles = re.findall(chapter_pattern, text)
    
    # Разделение текста на главы
    chapters = re.split(r"Глава \d+\.\s+[^\n]+", text)
    
    # Удаляем первый элемент, который содержит введение
    chapters = chapters[1:] if len(chapters) > 1 else []
    
    # Сопоставляем названия глав с их содержимым
    result = []
    for i, chapter_text in enumerate(chapters):
        if i < len(chapter_titles):
            result.append({
                "title": f"Глава {i+1}: {chapter_titles[i]}",
                "content": chapter_text.strip()
            })
    
    return result

# Функция для анализа главы с помощью Grok через OpenRouter
def analyze_chapter_with_grok(chapter):
    # Сначала ищем "Основные понятия" или "Саммари раздела" с перечислением понятий
    concepts_from_summary = []
    
    # Поиск секции "Основные понятия" в саммари раздела
    summary_match = re.search(r"Саммари раздела.*?Основные понятия:(.*?)(?=\n\n|\n[А-Я]|Моделирование:|Вопросы для повторения|$)", chapter['content'], re.DOTALL)
    
    if summary_match:
        concepts_text = summary_match.group(1).strip()
        print(f"Найдена секция 'Основные понятия' в саммари. Размер текста: {len(concepts_text)} символов")
        
        # Разделяем по запятым и очищаем
        raw_concepts = [c.strip() for c in concepts_text.split(',')]
        
        # Дополнительная очистка: удаляем строки без букв и слишком длинные строки
        for concept in raw_concepts:
            # Проверяем, что строка содержит буквы и не слишком длинная
            if re.search(r'[а-яА-Яa-zA-Z]', concept) and len(concept) < 50:
                concepts_from_summary.append(concept)
        
        print(f"Извлечено {len(concepts_from_summary)} понятий из саммари")
    else:
        print("Секция 'Основные понятия' в саммари не найдена")
        
        # Альтернативный поиск просто по фразе "Основные понятия:"
        basic_concepts_match = re.search(r"Основные понятия:(.*?)(?=\n\n|\n[А-Я]|$)", chapter['content'], re.DOTALL)
        if basic_concepts_match:
            concepts_text = basic_concepts_match.group(1).strip()
            print(f"Найдена отдельная секция 'Основные понятия'. Размер текста: {len(concepts_text)} символов")
            
            # Разделяем по запятым и очищаем
            raw_concepts = [c.strip() for c in concepts_text.split(',')]
            
            # Дополнительная очистка
            for concept in raw_concepts:
                if re.search(r'[а-яА-Яa-zA-Z]', concept) and len(concept) < 50:
                    concepts_from_summary.append(concept)
            
            print(f"Извлечено {len(concepts_from_summary)} понятий из секции 'Основные понятия'")
    
    # Если найдено больше 60 понятий, вероятно ошибка парсинга - посмотрим на уникальные понятия
    if len(concepts_from_summary) > 60:
        unique_concepts = list(set(concepts_from_summary))
        print(f"Слишком много понятий ({len(concepts_from_summary)}), вероятно дубликаты. Уникальных: {len(unique_concepts)}")
        concepts_from_summary = unique_concepts
    
    # Выводим список первых 10 понятий для проверки
    if concepts_from_summary:
        print("Примеры найденных понятий:", concepts_from_summary[:10])
    
    # Формируем промпт для Grok с учетом найденных понятий
    all_found_concepts = []  # Список всех понятий для сохранения
    
    # Ограничиваем размер текста главы до 5000 символов для надежности
    chapter_content = chapter['content'][:5000]
    
    prompt = f"""
Проанализируй следующую главу из курса по системному мышлению:

Название: {chapter['title']}

Содержание (первые 5000 символов):
{chapter_content}

"""

    # Если найдены понятия из саммари, добавляем их в промпт
    if concepts_from_summary:
        # Сохраняем полный список всех найденных понятий
        all_found_concepts = concepts_from_summary.copy()
        
        # Для промпта используем ограниченное количество понятий (API-запрос имеет ограничения)
        concepts_to_analyze = concepts_from_summary[:30] if len(concepts_from_summary) > 30 else concepts_from_summary
        
        prompt += f"""
В этой главе определены следующие основные понятия: {', '.join(concepts_to_analyze)}.

Для каждого из этих понятий необходимо:
1. Найти определение из текста главы
2. Найти пример использования из текста главы
3. Сформулировать 2-3 вопроса для проверки понимания

Если для какого-то понятия невозможно найти определение или пример в тексте, укажи это.
"""
    else:
        prompt += """
Выполни следующие задачи:
1. Найди все ключевые понятия, упомянутые в главе (особенно обрати внимание на раздел "Основные понятия" если он есть)
2. Для каждого понятия найди его определение из текста
3. Для каждого понятия найди пример использования из текста
4. Для каждого понятия сформулируй 2-3 вопроса для проверки понимания
"""

    # Общая часть промпта для всех случаев
    prompt += """
Также выполни следующие задачи:
1. Выдели 3 главные мысли главы
2. Найди как можно больше связей между понятиями по следующим типам:
   - RELATES_TO (связано с) - общая связь между понятиями
   - PART_OF (является частью) - отношение часть-целое
   - IS_A (является) - отношение "является"/"тип"
   - PREREQUISITE_FOR (необходимо для) - понятие A необходимо понять перед понятием B
   - EXAMPLE_OF (пример) - понятие A является примером понятия B
   - CONTRASTS_WITH (противоположно) - противоположные понятия
   - EVOLVED_FROM (развилось из) - историческое развитие
   - USED_IN (используется в) - применение понятия в контексте

Очень важно найти хотя бы 15-20 связей между понятиями, так как эти связи будут использоваться для построения знаниевого графа. Старайся связать как можно больше разных понятий друг с другом.

Результат представь в формате JSON со следующей структурой:
{{
  "main_ideas": ["идея 1", "идея 2", "идея 3"],
  "concepts": [
    {{
      "name": "Название понятия",
      "definition": "Определение понятия из текста",
      "example": "Пример использования из текста",
      "questions": ["Вопрос 1", "Вопрос 2", "Вопрос 3"]
    }}
  ],
  "relationships": [
    {{
      "source": "Понятие-источник",
      "target": "Понятие-цель",
      "type": "ТИП_СВЯЗИ",
      "description": "Описание связи"
    }}
  ]
}}

Отвечай только в формате JSON, без дополнительного текста.
"""

    try:
        # Добавляем повторные попытки в случае ошибки
        max_attempts = 3
        current_attempt = 0
        
        while current_attempt < max_attempts:
            try:
                current_attempt += 1
                print(f"Попытка {current_attempt} из {max_attempts} запроса к API")
                
                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://adapter-course.ru",
                        "X-Title": "Adapter Course",
                    },
                    json={
                        "model": AI_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 3000,
                        "temperature": 0.7
                    },
                    timeout=180  # Уменьшенный таймаут для надежности
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result['choices'][0]['message']['content']
                    
                    # Извлекаем JSON из ответа
                    try:
                        # Попробуем найти JSON в ответе
                        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                        if json_match:
                            content = json_match.group(1)
                        
                        parsed_data = json.loads(content)
                        
                        # Добавляем информацию о всех найденных понятиях
                        if all_found_concepts:
                            # Получаем список понятий, которые уже проанализированы моделью
                            analyzed_concepts = [concept["name"] for concept in parsed_data.get("concepts", [])]
                            
                            # Добавляем базовые записи для понятий, которые не были проанализированы
                            for concept_name in all_found_concepts:
                                if concept_name not in analyzed_concepts:
                                    parsed_data.setdefault("concepts", []).append({
                                        "name": concept_name,
                                        "definition": "Определение не найдено в тексте",
                                        "example": "Пример не найден в тексте",
                                        "questions": ["Вопрос на понимание понятия не сформулирован"]
                                    })
                            
                            # Сохраняем в результате список всех найденных понятий
                            parsed_data["all_found_concepts"] = all_found_concepts
                        
                        # Генерируем дополнительные связи между понятиями, если их мало
                        parsed_data = generate_additional_relationships(parsed_data)
                        
                        return parsed_data
                    except json.JSONDecodeError:
                        print(f"Ошибка при разборе JSON для главы {chapter['title']}")
                        print(f"Ответ API: {content[:200]}...")  # Печатаем только начало для отладки
                        
                        if current_attempt < max_attempts:
                            print(f"Повторная попытка через 5 секунд...")
                            time.sleep(5)
                            continue
                        else:
                            return None
                else:
                    print(f"Ошибка API: {response.status_code}")
                    if hasattr(response, 'text'):
                        print(f"Текст ошибки: {response.text[:200]}...")
                    
                    if current_attempt < max_attempts:
                        print(f"Повторная попытка через 5 секунд...")
                        time.sleep(5)
                        continue
                    else:
                        return None
                
            except requests.exceptions.RequestException as e:
                print(f"Сетевая ошибка при обращении к API: {str(e)}")
                
                if current_attempt < max_attempts:
                    print(f"Повторная попытка через 5 секунд...")
                    time.sleep(5)
                    continue
                else:
                    return None
                
        return None  # Если все попытки не удались
            
    except Exception as e:
        print(f"Ошибка при обработке главы {chapter['title']}: {str(e)}")
        return None

def generate_additional_relationships(parsed_data):
    """Генерирует дополнительные связи между понятиями, если модель вернула мало связей"""
    concepts = parsed_data.get("concepts", [])
    relationships = parsed_data.get("relationships", [])
    
    # Если связей меньше 10, добавляем базовые связи RELATES_TO между понятиями
    if len(relationships) < 10 and len(concepts) > 5:
        print("Недостаточно связей, добавляем базовые связи RELATES_TO между понятиями")
        
        # Берем первые 10 понятий с определениями (если таковых больше 5)
        defined_concepts = [c for c in concepts if c.get("definition") and c.get("definition") != "Определение не найдено в тексте"]
        defined_concepts = defined_concepts[:10] if len(defined_concepts) > 10 else defined_concepts
        
        # Если у нас есть хотя бы 3 понятия с определениями, создаем связи между ними
        if len(defined_concepts) >= 3:
            # Создаем базовые связи между понятиями
            for i in range(len(defined_concepts) - 1):
                for j in range(i + 1, len(defined_concepts)):
                    source = defined_concepts[i]["name"]
                    target = defined_concepts[j]["name"]
                    
                    # Проверяем, что такой связи еще нет
                    if not any(r.get("source") == source and r.get("target") == target for r in relationships) and \
                       not any(r.get("source") == target and r.get("target") == source for r in relationships):
                        relationships.append({
                            "source": source,
                            "target": target,
                            "type": "RELATES_TO",
                            "description": f"Понятия '{source}' и '{target}' связаны между собой в рамках этой главы"
                        })
        
        print(f"Добавлено {len(relationships) - len(parsed_data.get('relationships', []))} новых связей")
    
    # Обновляем раздел relationships в данных
    parsed_data["relationships"] = relationships
    return parsed_data

# Функция для загрузки данных в Neo4j
def load_to_neo4j(chapters_data, course_name="Системное саморазвитие"):
    """Загружает результаты анализа в базу данных Neo4j для указанного курса"""
    try:
        # Подключение к Neo4j
        graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        # Найдем узел курса
        course_node = graph.nodes.match("Course", name=course_name).first()
        if not course_node:
            print(f"Ошибка: Курс '{course_name}' не найден в базе данных")
            return False
        
        print(f"Загрузка данных в курс '{course_name}'")
        
        # Словарь для хранения созданных узлов по имени
        nodes_cache = {}
        
        # Счетчики
        chapter_count = 0
        concept_count = 0
        relationship_count = 0
        
        # Обрабатываем данные по каждой главе
        for i, chapter_info in enumerate(chapters_data):
            if not chapter_info:
                continue  # Пропускаем пустые данные
            
            chapter_title = chapter_info.get("title", f"Глава {i+1}")
            chapter_data = chapter_info.get("analysis", {})
            
            if not chapter_data:
                continue  # Пропускаем главы без анализа
            
            # Создаем узел главы
            chapter_node = Node("Chapter", 
                              title=chapter_title,
                              main_ideas=chapter_data.get("main_ideas", []),
                              course=course_name)  # Добавляем атрибут course
            graph.create(chapter_node)
            chapter_count += 1
            
            # Связываем главу с узлом курса
            rel = Relationship(chapter_node, "PART_OF", course_node,
                             description=f"Глава {i+1} курса {course_name}")
            graph.create(rel)
            
            # Создаем узлы понятий и связываем их с главой
            for concept in chapter_data.get("concepts", []):
                concept_name = concept["name"]
                
                # Проверяем, есть ли уже такое понятие
                concept_node = graph.nodes.match("Concept", name=concept_name).first()
                
                if not concept_node:
                    # Создаем новый узел понятия
                    concept_node = Node("Concept",
                                      name=concept_name,
                                      definition=concept.get("definition", ""),
                                      example=concept.get("example", ""),
                                      questions=concept.get("questions", []))
                    graph.create(concept_node)
                    concept_count += 1
                elif concept.get("definition") and not concept_node.get("definition"):
                    # Обновляем существующий узел, если в нем нет определения
                    concept_node["definition"] = concept.get("definition")
                    concept_node["example"] = concept.get("example", "")
                    concept_node["questions"] = concept.get("questions", [])
                    graph.push(concept_node)
                
                # Сохраняем узел в кэше для использования при создании связей
                nodes_cache[concept_name] = concept_node
                
                # Проверяем, существует ли уже связь между понятием и главой
                rel_matcher = RelationshipMatcher(graph)
                existing_rel = rel_matcher.match(
                    (concept_node, chapter_node), 
                    r_type="MENTIONED_IN"
                ).first()
                
                if not existing_rel:
                    # Создаем связь "MENTIONED_IN" между понятием и главой
                    rel = Relationship(concept_node, "MENTIONED_IN", chapter_node,
                                     description=f"Понятие {concept_name} упоминается в главе {i+1} курса {course_name}")
                    graph.create(rel)
                    relationship_count += 1
                
                # Также создаем связь PART_OF между понятием и узлом курса
                existing_rel_course = rel_matcher.match(
                    (concept_node, course_node), 
                    r_type="PART_OF"
                ).first()
                
                if not existing_rel_course:
                    rel_course = Relationship(concept_node, "PART_OF", course_node,
                                           description=f"Понятие {concept_name} является частью курса {course_name}")
                    graph.create(rel_course)
                    relationship_count += 1
            
            # Создаем связи между понятиями
            for rel_data in chapter_data.get("relationships", []):
                source_name = rel_data["source"]
                target_name = rel_data["target"]
                rel_type = rel_data["type"]
                
                # Проверяем, есть ли понятия в кэше или в базе
                source_node = nodes_cache.get(source_name)
                if not source_node:
                    source_node = graph.nodes.match("Concept", name=source_name).first()
                    if source_node:
                        nodes_cache[source_name] = source_node
                
                target_node = nodes_cache.get(target_name)
                if not target_node:
                    target_node = graph.nodes.match("Concept", name=target_name).first()
                    if target_node:
                        nodes_cache[target_name] = target_node
                
                # Если оба понятия найдены, создаем связь между ними
                if source_node and target_node:
                    # Проверяем, существует ли уже такая связь
                    existing_rel = rel_matcher.match(
                        (source_node, target_node), 
                        r_type=rel_type
                    ).first()
                    
                    if not existing_rel:
                        rel = Relationship(source_node, rel_type, target_node,
                                         description=rel_data.get("description", ""))
                        graph.create(rel)
                        relationship_count += 1
        
        print(f"Загрузка в Neo4j завершена: создано {chapter_count} глав, {concept_count} понятий, {relationship_count} связей")
        return True
        
    except Exception as e:
        print(f"Ошибка при загрузке данных в Neo4j: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Анализ курса с помощью Grok AI и запись в Neo4j")
    parser.add_argument("--course", type=str, default="Системное саморазвитие", help="Название курса")
    parser.add_argument("--file", type=str, default=COURSE_FILE, help="Путь к файлу курса")
    parser.add_argument("--course-format", type=str, default="auto", 
                        choices=["auto", "chapter-based", "glossary-based"],
                        help="Формат курса: auto - автоопределение, chapter-based - понятия в главах, glossary-based - список понятий в конце")
    args = parser.parse_args()
    
    course_name = args.course
    course_file = args.file
    
    # Определение формата курса
    course_format = None
    if args.course_format != "auto":
        course_format = args.course_format
    else:
        course_format = get_course_format(course_file)
    
    print(f"Анализ курса '{course_name}' из файла '{course_file}'")
    print(f"Формат курса: {course_format}")
    
    try:
        # Чтение текста курса
        course_text = read_course_file(course_file)
        
        # Подключение к Neo4j
        graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        # Поиск корневого узла курса
        course_node = graph.nodes.match("Course", name=course_name).first()
        if not course_node:
            print(f"Создание узла для курса '{course_name}'...")
            course_node = Node("Course", name=course_name, description=f"Курс {course_name}")
            graph.create(course_node)
        
        # Для курса с понятиями в главах используем обычный анализ
        if course_format == "chapter-based":
            # Разделение текста курса на главы
            chapters = split_into_chapters(course_text)
            print(f"Найдено {len(chapters)} глав в курсе")
            
            # Анализ каждой главы и сохранение результатов
            chapters_data = []
            for i, chapter in enumerate(chapters):
                print(f"\nАнализ главы {i+1}/{len(chapters)}: {chapter['title']}")
                chapter_analysis = analyze_chapter_with_grok(chapter)
                
                # Генерация дополнительных связей между понятиями
                chapter_analysis = generate_additional_relationships(chapter_analysis)
                
                chapters_data.append({
                    "title": chapter["title"],
                    "analysis": chapter_analysis
                })
                
                # Сохранение промежуточных результатов в JSON-файл
                results_dir = "results"
                if not os.path.exists(results_dir):
                    os.makedirs(results_dir)
                
                results_file = os.path.join(results_dir, f"chapter_{i+1}_analysis.json")
                with open(results_file, "w", encoding="utf-8") as f:
                    json.dump(chapter_analysis, f, ensure_ascii=False, indent=2)
                print(f"Результаты анализа сохранены в {results_file}")
            
            # Загрузка результатов в Neo4j
            load_to_neo4j(chapters_data, course_name)
            print(f"Анализ курса '{course_name}' успешно завершен и данные загружены в Neo4j")
        
        # Для курса с глоссарием в конце используем анализ понятий из глоссария
        else:  # course_format == "glossary-based"
            # Извлечение понятий из курса
            concepts = extract_course_concepts(course_file, course_format)
            print(f"Извлечено {len(concepts)} понятий из глоссария")
            
            # Создание узлов понятий в Neo4j
            for concept_name in concepts:
                # Проверяем, существует ли уже такое понятие в базе
                concept_node = graph.nodes.match("Concept", name=concept_name).first()
                if not concept_node:
                    print(f"Создание узла для понятия '{concept_name}'...")
                    concept_node = Node("Concept", name=concept_name)
                    graph.create(concept_node)
                    
                    # Связываем понятие с курсом
                    rel = Relationship(concept_node, "PART_OF", course_node)
                    graph.create(rel)
                elif not graph.exists(Relationship(concept_node, "PART_OF", course_node)):
                    # Если понятие уже существует, но не связано с текущим курсом
                    rel = Relationship(concept_node, "PART_OF", course_node)
                    graph.create(rel)
            
            print(f"Все понятия из глоссария успешно добавлены в Neo4j")
            
            # Сохранение списка понятий в JSON-файл
            results_dir = "results"
            if not os.path.exists(results_dir):
                os.makedirs(results_dir)
            
            results_file = os.path.join(results_dir, f"glossary_concepts.json")
            with open(results_file, "w", encoding="utf-8") as f:
                json.dump(concepts, f, ensure_ascii=False, indent=2)
            print(f"Список понятий сохранен в {results_file}")
            
            # Для связывания понятий и их анализа мы используем отдельный скрипт
            print(f"Для анализа понятий и создания связей между ними используйте скрипт analyze_concepts_in_depth.py")
    
    except Exception as e:
        print(f"Ошибка при анализе курса: {str(e)}")

if __name__ == "__main__":
    main() 