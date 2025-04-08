#!/usr/bin/env python
# -*- coding: utf-8 -*-

from py2neo import Graph, Node, Relationship
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Конфигурация подключения к Neo4j
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j")

def create_course(course_name, course_description=None):
    """Создает новый корневой узел курса в Neo4j, не удаляя существующие данные"""
    if not course_description:
        course_description = f"Курс {course_name}"
    
    try:
        # Подключение к Neo4j
        graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        # Проверяем, существует ли уже такой курс
        existing_course = graph.nodes.match("Course", name=course_name).first()
        if existing_course:
            print(f"Курс '{course_name}' уже существует в базе данных")
            return existing_course
        
        # Создаем новый узел курса
        print(f"Создание корневого узла для курса '{course_name}'...")
        course_node = Node("Course", name=course_name, description=course_description)
        graph.create(course_node)
        
        print(f"Корневой узел для курса '{course_name}' успешно создан")
        print(f"URI для подключения: {NEO4J_URI}")
        return course_node
    except Exception as e:
        print(f"Ошибка при создании курса: {str(e)}")
        return None

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        course_name = sys.argv[1]
        description = sys.argv[2] if len(sys.argv) > 2 else None
        create_course(course_name, description)
    else:
        print("Использование: python create_course.py 'Название курса' ['Описание курса']")
        print("Пример: python create_course.py 'Практики саморазвития' 'Курс по практическим методам саморазвития'") 