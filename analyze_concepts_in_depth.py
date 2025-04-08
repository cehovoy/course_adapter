#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import re
import time
import requests
import argparse
from py2neo import Graph, Node, Relationship, NodeMatcher, RelationshipMatcher
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
RESULTS_DIR = os.getenv("RESULTS_DIR", "results") + "/concepts"
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "20"))
MAX_CONCEPTS_TO_ANALYZE = int(os.getenv("MAX_CONCEPTS_TO_ANALYZE", "500"))
AI_MODEL = os.getenv("AI_MODEL", "x-ai/grok-2-1212")

# Проверка наличия необходимых переменных
if not OPENROUTER_API_KEY:
    raise ValueError("Отсутствует OPENROUTER_API_KEY. Проверьте файл .env")

# Функция для чтения текста курса
def read_course_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        print(f"Ошибка при чтении файла курса: {str(e)}")
        return None

def ensure_results_dir():
    """Убедитесь, что директория для результатов существует"""
    if not os.path.exists(RESULTS_DIR):
        os.makedirs(RESULTS_DIR)
        print(f"Создана директория {RESULTS_DIR} для сохранения результатов")

# Функция для получения всех понятий без определений для конкретного курса
def get_undefined_concepts(course_name, graph=None):
    try:
        if not graph:
            graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        # Находим курс
        course = graph.nodes.match("Course", name=course_name).first()
        if not course:
            print(f"Ошибка: Курс '{course_name}' не найден")
            return []
        
        # Получаем все понятия, связанные с курсом
        cypher = """
        MATCH (c:Course {name: $course_name})<-[:PART_OF]-(concept:Concept)
        WHERE concept.definition IS NULL OR concept.definition = ''
        RETURN concept.name AS name
        LIMIT $limit
        """
        
        result = graph.run(cypher, course_name=course_name, limit=MAX_CONCEPTS_TO_ANALYZE).data()
        concepts = [item["name"] for item in result]
        
        print(f"Найдено {len(concepts)} понятий без определений для курса '{course_name}'")
        return concepts
    except Exception as e:
        print(f"Ошибка при получении понятий без определений: {str(e)}")
        return []

# Функция для анализа понятия с помощью API Grok
def analyze_concept_with_api(concept_name, defined_concepts, course_text, course_name):
    print(f"\nАнализ понятия: {concept_name}")
    
    # Контекст для анализа понятия
    # Ищем контекст упоминания понятия в тексте курса
    search_pattern = r'(?i)(?:[^\w]|^)' + re.escape(concept_name) + r'(?:[^\w]|$)'
    matches = list(re.finditer(search_pattern, course_text))
    
    # Получаем контекст из каждого упоминания (300 символов до и после)
    contexts = []
    for match in matches[:5]:  # Ограничиваем количество контекстов
        start = max(0, match.start() - 300)
        end = min(len(course_text), match.end() + 300)
        context = course_text[start:end]
        contexts.append(context)
    
    # Объединяем контексты
    context_text = "\n---\n".join(contexts)
    
    # Список уже определенных понятий для использования в промпте
    defined_list = ", ".join(defined_concepts)
    
    # Подготовка промпта для API
    prompt = f"""
    Ты эксперт по системному мышлению. Я прохожу курс '{course_name}' и хочу лучше понять понятие "{concept_name}".
    
    Вот несколько упоминаний этого понятия в тексте курса:
    
    {context_text}
    
    В курсе уже определены следующие понятия: {defined_list}
    
    Пожалуйста, дай мне информацию о понятии "{concept_name}" в следующем JSON-формате:
    
    {{
        "name": "название понятия",
        "definition": "подробное определение понятия",
        "example": "практический пример использования понятия",
        "questions": ["вопрос для проверки понимания 1", "вопрос для проверки понимания 2", "вопрос для проверки понимания 3"],
        "related_concepts": [
            {{"name": "связанное понятие 1", "relationship_type": "тип связи", "description": "описание связи"}},
            {{"name": "связанное понятие 2", "relationship_type": "тип связи", "description": "описание связи"}}
        ]
    }}
    
    Типы связей могут быть: RELATES_TO, PART_OF, IS_A, PREREQUISITE_FOR, EXAMPLE_OF, CONTRASTS_WITH, EVOLVED_FROM, USED_IN.
    
    Твоя задача - помочь мне глубоко понять это понятие в контексте системного мышления и связать его с другими понятиями курса.
    """
    
    # API запрос к Grok через OpenRouter
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            print(f"Попытка {attempt + 1} из {max_attempts} запроса к API")
            
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
                    "max_tokens": 2000,
                    "temperature": 0.7
                },
                timeout=60
            )
            
            if response.status_code == 200:
                response_data = response.json()
                if "choices" in response_data and len(response_data["choices"]) > 0:
                    message_content = response_data["choices"][0]["message"]["content"]
                    
                    # Попытка извлечь JSON из ответа
                    try:
                        # Найти JSON в ответе
                        json_pattern = r'```json\s*([\s\S]*?)\s*```|```\s*([\s\S]*?)\s*```|(\{[\s\S]*\})'
                        json_match = re.search(json_pattern, message_content)
                        
                        if json_match:
                            # Определяем, какая группа содержит JSON
                            for group in range(1, 4):
                                if json_match.group(group):
                                    json_str = json_match.group(group)
                                    break
                        else:
                            # Если не нашли JSON в кодовых блоках, попробуем найти объект напрямую
                            json_str = message_content
                        
                        # Очистка от возможных дополнительных символов
                        json_str = json_str.strip()
                        result = json.loads(json_str)
                        print(f"Анализ понятия '{concept_name}' успешно завершен")
                        return result
                    except json.JSONDecodeError:
                        print(f"Не удалось извлечь JSON из ответа API. Попытка {attempt + 1}")
                        print("Ответ API:", message_content[:100] + "..." if len(message_content) > 100 else message_content)
                else:
                    print(f"Отсутствуют данные в ответе API. Попытка {attempt + 1}")
            else:
                print(f"Ошибка API запроса: {response.status_code}. Попытка {attempt + 1}")
                print(response.text)
            
            # Если это была не последняя попытка, подождем перед следующей
            if attempt < max_attempts - 1:
                time.sleep(5 * (attempt + 1))  # Увеличиваем время ожидания с каждой попыткой
                
        except Exception as e:
            print(f"Ошибка при выполнении API запроса: {str(e)}. Попытка {attempt + 1}")
            
            # Если это была не последняя попытка, подождем перед следующей
            if attempt < max_attempts - 1:
                time.sleep(5 * (attempt + 1))
    
    print(f"Не удалось проанализировать понятие '{concept_name}' после {max_attempts} попыток")
    return None

# Функция для обновления понятия в базе данных
def update_concept_in_db(concept_data, course_name, graph=None):
    if not graph:
        graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    try:
        # Получаем курс
        course = graph.nodes.match("Course", name=course_name).first()
        if not course:
            print(f"Ошибка: Курс '{course_name}' не найден")
            return False
        
        matcher = NodeMatcher(graph)
        rel_matcher = RelationshipMatcher(graph)
        
        # Находим узел понятия
        concept_name = concept_data["name"]
        concept_node = matcher.match("Concept", name=concept_name).first()
        
        if not concept_node:
            # Создаем новый узел
            concept_node = Node("Concept", 
                              name=concept_name,
                              definition=concept_data.get("definition", ""),
                              example=concept_data.get("example", ""),
                              questions=concept_data.get("questions", []))
            graph.create(concept_node)
            
            # Создаем связь с курсом
            course_rel = Relationship(concept_node, "PART_OF", course,
                                    description=f"Понятие {concept_name} является частью курса {course_name}")
            graph.create(course_rel)
            print(f"Создан новый узел понятия '{concept_name}'")
        else:
            # Обновляем существующий узел
            concept_node["definition"] = concept_data.get("definition", concept_node.get("definition", ""))
            concept_node["example"] = concept_data.get("example", concept_node.get("example", ""))
            concept_node["questions"] = concept_data.get("questions", concept_node.get("questions", []))
            graph.push(concept_node)
            
            # Проверяем связь с курсом
            existing_rel = rel_matcher.match((concept_node, course), r_type="PART_OF").first()
            if not existing_rel:
                course_rel = Relationship(concept_node, "PART_OF", course,
                                        description=f"Понятие {concept_name} является частью курса {course_name}")
                graph.create(course_rel)
            
            print(f"Обновлен узел понятия '{concept_name}'")
        
        # Создаем связи с другими понятиями
        relationship_count = 0
        for rel_data in concept_data.get("related_concepts", []):
            related_name = rel_data.get("name")
            rel_type = rel_data.get("relationship_type", "RELATES_TO")
            description = rel_data.get("description", "")
            
            if not related_name:
                continue
            
            # Находим или создаем связанное понятие
            related_node = matcher.match("Concept", name=related_name).first()
            if not related_node:
                related_node = Node("Concept", name=related_name)
                graph.create(related_node)
                
                # Создаем связь с курсом
                course_rel = Relationship(related_node, "PART_OF", course,
                                        description=f"Понятие {related_name} является частью курса {course_name}")
                graph.create(course_rel)
                
                print(f"Создан новый узел для связанного понятия '{related_name}'")
            
            # Проверяем, существует ли уже связь между понятиями
            existing_rel = rel_matcher.match((concept_node, related_node), r_type=rel_type).first()
            if not existing_rel:
                rel = Relationship(concept_node, rel_type, related_node, description=description)
                graph.create(rel)
                relationship_count += 1
        
        print(f"Создано {relationship_count} новых связей для понятия '{concept_name}'")
        return True
    
    except Exception as e:
        print(f"Ошибка при обновлении понятия в Neo4j: {str(e)}")
        return False

def analyze_batch_of_concepts(concepts, course_text, course_name, graph=None):
    """Анализирует партию понятий"""
    if not graph:
        graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    # Получаем список понятий, у которых уже есть определения
    cypher = """
    MATCH (c:Course {name: $course_name})<-[:PART_OF]-(concept:Concept)
    WHERE concept.definition IS NOT NULL AND concept.definition <> ''
    RETURN concept.name AS name
    """
    
    result = graph.run(cypher, course_name=course_name).data()
    defined_concepts = [item["name"] for item in result]
    
    print(f"Найдено {len(defined_concepts)} понятий с определениями для использования в анализе")
    
    # Анализируем каждое понятие в партии
    success_count = 0
    for concept_name in concepts:
        # Проверяем, не было ли понятие определено другим процессом
        if concept_name in defined_concepts:
            print(f"Понятие '{concept_name}' уже имеет определение, пропускаем")
            continue
            
        # Анализируем понятие
        concept_data = analyze_concept_with_api(concept_name, defined_concepts, course_text, course_name)
        
        if concept_data and "name" in concept_data:
            # Сохраняем результаты анализа
            ensure_results_dir()
            result_file = os.path.join(RESULTS_DIR, f"concept_{concept_name.replace(' ', '_')}.json")
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(concept_data, f, ensure_ascii=False, indent=2)
            
            # Обновляем понятие в базе данных
            if update_concept_in_db(concept_data, course_name, graph):
                success_count += 1
                defined_concepts.append(concept_name)  # Добавляем в список для следующих анализов
        
        # Пауза между запросами
        time.sleep(3)
    
    return success_count

def analyze_all_undefined_concepts(course_name, course_file=None):
    """Анализирует все понятия без определений в заданном курсе"""
    try:
        # Подключение к Neo4j
        graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        # Проверяем существование курса
        course = graph.nodes.match("Course", name=course_name).first()
        if not course:
            print(f"Ошибка: Курс '{course_name}' не найден")
            return False
        
        # Получаем понятия без определений
        undefined_concepts = get_undefined_concepts(course_name, graph)
        
        if not undefined_concepts:
            print(f"Все понятия курса '{course_name}' уже имеют определения")
            return True
        
        # Получаем текст курса
        if not course_file:
            course_file = COURSE_FILE
        
        course_text = read_course_file(course_file)
        if not course_text:
            print(f"Не удалось прочитать файл курса '{course_file}'")
            return False
        
        # Разбиваем понятия на партии
        batches = [undefined_concepts[i:i+BATCH_SIZE] for i in range(0, len(undefined_concepts), BATCH_SIZE)]
        
        # Анализируем каждую партию
        total_success = 0
        for i, batch in enumerate(batches):
            print(f"\nОбработка партии {i+1} из {len(batches)} ({len(batch)} понятий)")
            success_count = analyze_batch_of_concepts(batch, course_text, course_name, graph)
            total_success += success_count
            
            # Пауза между партиями для соблюдения ограничений API
            if i < len(batches) - 1:
                print(f"Пауза перед следующей партией...")
                time.sleep(10)
        
        print(f"\nАнализ завершен! Успешно обработано {total_success} из {len(undefined_concepts)} понятий")
        return True
    
    except Exception as e:
        print(f"Ошибка при анализе понятий: {str(e)}")
        return False

def get_course_list():
    """Получает список всех курсов в базе данных"""
    try:
        # Подключение к Neo4j
        graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        # Запрос для получения всех курсов
        cypher_query = "MATCH (c:Course) RETURN c.name AS name"
        result = graph.run(cypher_query).data()
        
        courses = [record["name"] for record in result]
        return courses
    except Exception as e:
        print(f"Ошибка при получении списка курсов: {str(e)}")
        return []

def parse_args():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(description='Углубленный анализ понятий курса')
    parser.add_argument('--course', type=str, default="Системное саморазвитие",
                        help='Название курса (по умолчанию: "Системное саморазвитие")')
    parser.add_argument('--file', type=str, help='Путь к файлу с текстом курса')
    parser.add_argument('--list', action='store_true', help='Вывести список всех курсов')
    parser.add_argument('--course-format', type=str, default="auto", 
                        choices=["auto", "chapter-based", "glossary-based"],
                        help='Формат курса: auto - автоопределение, chapter-based - понятия в главах, glossary-based - список понятий в конце')
    parser.add_argument('--extract-concepts', action='store_true', 
                        help='Извлечь понятия из курса и добавить их в базу данных без их анализа')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    
    if args.list:
        print("Список доступных курсов:")
        courses = get_course_list()
        for i, course in enumerate(courses):
            print(f"{i+1}. {course}")
    elif args.extract_concepts:
        print(f"Извлечение понятий из курса: '{args.course}'")
        
        if not args.file:
            print("Ошибка: Необходимо указать файл курса с помощью параметра --file")
            exit(1)
            
        print(f"Используется файл курса: {args.file}")
        
        # Определение формата курса
        course_format = None
        if args.course_format != "auto":
            course_format = args.course_format
        else:
            course_format = get_course_format(args.file)
        
        print(f"Формат курса: {course_format}")
        
        # Извлечение понятий
        try:
            # Подключение к Neo4j
            graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            
            # Поиск корневого узла курса
            course_node = graph.nodes.match("Course", name=args.course).first()
            if not course_node:
                print(f"Создание узла для курса '{args.course}'...")
                course_node = Node("Course", name=args.course, description=f"Курс {args.course}")
                graph.create(course_node)
            
            # Извлечение понятий
            concepts = extract_course_concepts(args.file, course_format)
            print(f"Извлечено {len(concepts)} понятий из курса")
            
            # Создание узлов понятий в Neo4j
            created_count = 0
            linked_count = 0
            for concept_name in concepts:
                # Проверяем, существует ли уже такое понятие в базе
                concept_node = graph.nodes.match("Concept", name=concept_name).first()
                if not concept_node:
                    # Создаем новый узел
                    concept_node = Node("Concept", name=concept_name)
                    graph.create(concept_node)
                    created_count += 1
                    
                    # Связываем понятие с курсом
                    rel = Relationship(concept_node, "PART_OF", course_node)
                    graph.create(rel)
                    linked_count += 1
                elif not graph.exists(Relationship(concept_node, "PART_OF", course_node)):
                    # Если понятие уже существует, но не связано с текущим курсом
                    rel = Relationship(concept_node, "PART_OF", course_node)
                    graph.create(rel)
                    linked_count += 1
            
            print(f"Создано {created_count} новых узлов понятий и {linked_count} связей с курсом")
            
            # Сохранение списка понятий в JSON-файл
            results_dir = "results"
            if not os.path.exists(results_dir):
                os.makedirs(results_dir)
            
            results_file = os.path.join(results_dir, f"extracted_concepts_{args.course.replace(' ', '_')}.json")
            with open(results_file, "w", encoding="utf-8") as f:
                json.dump(concepts, f, ensure_ascii=False, indent=2)
            print(f"Список понятий сохранен в {results_file}")
            
        except Exception as e:
            print(f"Ошибка при извлечении понятий: {str(e)}")
    else:
        print(f"Запуск углубленного анализа понятий для курса: '{args.course}'")
        if args.file:
            print(f"Используется файл курса: {args.file}")
        
        course_file = args.file if args.file else None
        success = analyze_all_undefined_concepts(args.course, course_file)
        
        if success:
            print("\nАнализ понятий успешно завершен!")
        else:
            print("\nАнализ понятий завершен с ошибками") 