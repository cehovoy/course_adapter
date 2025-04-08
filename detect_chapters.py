#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import re
import requests
import argparse
from py2neo import Graph, Node, Relationship
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Параметры подключения
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
AI_MODEL = os.getenv("AI_MODEL", "x-ai/grok-2-1212")

def read_course_file(file_path):
    """Чтение файла курса"""
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()

def detect_chapters_with_ai(course_text, course_name):
    """Определение глав и понятий в тексте курса с помощью AI"""
    # Создаем промпт для определения глав в тексте
    prompt = f"""
    Я анализирую курс "{course_name}" и хочу разделить его на логические главы или разделы.
    
    В тексте курса нет явного деления на главы, но я хочу выделить основные темы и создать структуру.
    
    Вот первые 5000 символов текста курса для анализа:
    ```
    {course_text[:5000]}
    ```
    
    И вот последние 2000 символов для контекста:
    ```
    {course_text[-2000:]}
    ```
    
    Проанализируй структуру текста и выдели 7-12 логических глав/разделов.
    Для каждой главы определи её название, основные темы и 10-15 ключевых понятий, которые в ней обсуждаются.
    
    Результат верни в формате JSON:
    ```json
    [
      {{
        "title": "Название главы 1",
        "description": "Краткое описание главы",
        "concepts": [
          "Понятие 1",
          "Понятие 2",
          ...
        ]
      }},
      ...
    ]
    ```
    """
    
    # Отправка запроса к API
    try:
        print("Отправка запроса к API для выделения глав в курсе...")
        
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://adapter-course.ru",
                "X-Title": "Adapter Course"
            },
            json={
                "model": AI_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 3000,
                "temperature": 0.7
            },
            timeout=60
        )
        
        if response.status_code == 200:
            response_data = response.json()
            message_content = response_data["choices"][0]["message"]["content"]
            
            # Извлечение JSON из ответа
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```|```\s*([\s\S]*?)\s*```|(\[[\s\S]*\])', message_content)
            
            if json_match:
                # Определяем, какая группа содержит JSON
                for group in range(1, 4):
                    if json_match.group(group):
                        json_str = json_match.group(group)
                        break
            else:
                # Если не нашли JSON в кодовых блоках, попробуем найти массив напрямую
                json_str = message_content
            
            # Очистка от возможных дополнительных символов
            json_str = json_str.strip()
            result = json.loads(json_str)
            return result
        else:
            print(f"Ошибка API: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"Ошибка при запросе к API: {str(e)}")
        return None

def analyze_chapter_concepts(chapter, course_text, course_name):
    """Анализ понятий для выделенной главы с помощью AI"""
    # Поиск основного текста главы (приблизительно)
    chapter_title = chapter["title"]
    chapter_concepts = chapter.get("concepts", [])
    
    # Создаем промпт для анализа понятий главы
    prompt = f"""
    Я анализирую главу "{chapter_title}" из курса "{course_name}".
    
    Для этой главы были выделены следующие ключевые понятия:
    - {", ".join(chapter_concepts)}
    
    Пожалуйста, дай подробное определение для каждого из этих понятий и укажи связи между ними.
    
    Результат верни в формате JSON:
    ```json
    {{
      "concepts": [
        {{
          "name": "Название понятия",
          "definition": "Подробное определение понятия",
          "example": "Практический пример использования понятия",
          "questions": ["Вопрос для проверки понимания 1", "Вопрос для проверки понимания 2", "Вопрос для проверки понимания 3"]
        }},
        ...
      ],
      "relationships": [
        {{
          "source": "Понятие-источник",
          "target": "Понятие-цель",
          "type": "Тип связи",
          "description": "Описание связи"
        }},
        ...
      ]
    }}
    ```
    
    Типы связей могут быть: RELATES_TO, PART_OF, IS_A, PREREQUISITE_FOR, EXAMPLE_OF, CONTRASTS_WITH, EVOLVED_FROM, USED_IN.
    """
    
    # Отправка запроса к API
    try:
        print(f"Анализ понятий для главы '{chapter_title}'...")
        
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://adapter-course.ru",
                "X-Title": "Adapter Course"
            },
            json={
                "model": AI_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 3000,
                "temperature": 0.7
            },
            timeout=60
        )
        
        if response.status_code == 200:
            response_data = response.json()
            message_content = response_data["choices"][0]["message"]["content"]
            
            # Извлечение JSON из ответа
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```|```\s*([\s\S]*?)\s*```|(\{[\s\S]*\})', message_content)
            
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
            
            # Добавляем информацию о главе
            result["chapter_title"] = chapter_title
            result["chapter_description"] = chapter.get("description", "")
            
            return result
        else:
            print(f"Ошибка API: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"Ошибка при запросе к API: {str(e)}")
        return None

def create_chapters_in_neo4j(chapters_data, course_name, graph=None):
    """Создание структуры глав и понятий в Neo4j"""
    if graph is None:
        graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    # Получаем узел курса
    course_node = graph.nodes.match("Course", name=course_name).first()
    if not course_node:
        print(f"Ошибка: Курс '{course_name}' не найден")
        return False
    
    # Создаем главы и понятия
    for chapter in chapters_data:
        chapter_title = chapter["chapter_title"]
        chapter_description = chapter.get("chapter_description", "")
        
        # Создаем узел главы
        chapter_node = Node("Chapter",
                           title=chapter_title,
                           description=chapter_description,
                           course=course_name)
        graph.create(chapter_node)
        
        # Связываем главу с курсом
        rel = Relationship(chapter_node, "PART_OF", course_node,
                          description=f"Глава '{chapter_title}' является частью курса '{course_name}'")
        graph.create(rel)
        
        print(f"Создана глава '{chapter_title}' и связана с курсом")
        
        # Создаем понятия и связываем их с главой
        concepts_count = 0
        for concept_data in chapter.get("concepts", []):
            concept_name = concept_data["name"]
            
            # Проверяем, существует ли уже такое понятие
            concept_node = graph.nodes.match("Concept", name=concept_name).first()
            
            if not concept_node:
                # Создаем новый узел понятия
                concept_node = Node("Concept",
                                  name=concept_name,
                                  definition=concept_data.get("definition", ""),
                                  example=concept_data.get("example", ""),
                                  questions=concept_data.get("questions", []))
                graph.create(concept_node)
                
                # Связываем понятие с курсом
                course_rel = Relationship(concept_node, "PART_OF", course_node,
                                        description=f"Понятие '{concept_name}' является частью курса '{course_name}'")
                graph.create(course_rel)
            else:
                # Обновляем существующий узел, если нет определения
                if not concept_node.get("definition") and concept_data.get("definition"):
                    concept_node["definition"] = concept_data.get("definition")
                    concept_node["example"] = concept_data.get("example", "")
                    concept_node["questions"] = concept_data.get("questions", [])
                    graph.push(concept_node)
            
            # Связываем понятие с главой (MENTIONED_IN)
            if not graph.exists(Relationship(concept_node, "MENTIONED_IN", chapter_node)):
                chapter_rel = Relationship(concept_node, "MENTIONED_IN", chapter_node,
                                         description=f"Понятие '{concept_name}' упоминается в главе '{chapter_title}'")
                graph.create(chapter_rel)
                concepts_count += 1
        
        print(f"  Связано {concepts_count} понятий с главой '{chapter_title}'")
        
        # Создаем связи между понятиями
        relationships_count = 0
        for rel_data in chapter.get("relationships", []):
            source_name = rel_data["source"]
            target_name = rel_data["target"]
            rel_type = rel_data["type"]
            description = rel_data.get("description", "")
            
            # Находим узлы понятий
            source_node = graph.nodes.match("Concept", name=source_name).first()
            target_node = graph.nodes.match("Concept", name=target_name).first()
            
            if source_node and target_node:
                # Проверяем, существует ли уже такая связь
                if not graph.exists(Relationship(source_node, rel_type, target_node)):
                    rel = Relationship(source_node, rel_type, target_node, description=description)
                    graph.create(rel)
                    relationships_count += 1
        
        print(f"  Создано {relationships_count} связей между понятиями")
    
    return True

def main():
    parser = argparse.ArgumentParser(description="Выявление структуры глав в курсе")
    parser.add_argument("--course", type=str, required=True, help="Название курса")
    parser.add_argument("--file", type=str, required=True, help="Путь к файлу курса")
    args = parser.parse_args()
    
    # Подключение к Neo4j
    graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    # Чтение текста курса
    course_text = read_course_file(args.file)
    print(f"Файл курса '{args.file}' успешно прочитан: {len(course_text)} символов")
    
    # Определение глав в тексте курса
    chapters = detect_chapters_with_ai(course_text, args.course)
    
    if not chapters:
        print("Не удалось выделить главы в тексте курса")
        return
    
    # Сохраняем результаты выделения глав
    results_dir = "results"
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    
    chapters_file = os.path.join(results_dir, f"chapters_{args.course.replace(' ', '_')}.json")
    with open(chapters_file, "w", encoding="utf-8") as f:
        json.dump(chapters, f, ensure_ascii=False, indent=2)
    print(f"Результаты выделения глав сохранены в {chapters_file}")
    
    # Анализ понятий для каждой главы
    chapters_data = []
    for chapter in chapters:
        chapter_analysis = analyze_chapter_concepts(chapter, course_text, args.course)
        
        if chapter_analysis:
            chapters_data.append(chapter_analysis)
            
            # Сохраняем результаты анализа главы
            chapter_file = os.path.join(results_dir, f"chapter_{chapter['title'].replace(' ', '_')}.json")
            with open(chapter_file, "w", encoding="utf-8") as f:
                json.dump(chapter_analysis, f, ensure_ascii=False, indent=2)
            print(f"Результаты анализа главы '{chapter['title']}' сохранены")
    
    # Создаем структуру в Neo4j
    if chapters_data:
        create_chapters_in_neo4j(chapters_data, args.course, graph)
        print(f"Структура курса '{args.course}' успешно создана в Neo4j")
    else:
        print("Не удалось проанализировать понятия глав")

if __name__ == "__main__":
    main() 