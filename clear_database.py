#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import argparse
from py2neo import Graph
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Параметры подключения к Neo4j
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j")

def clear_database(force=False):
    """
    Полностью очищает базу данных Neo4j, удаляя все узлы и связи.
    
    Parameters:
    - force: если True, очищает без подтверждения (опасно)
    """
    try:
        # Подключение к Neo4j
        graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        print(f"Соединение с Neo4j установлено: {NEO4J_URI}")
        
        # Получение количества узлов и связей перед очисткой
        nodes_count = graph.run("MATCH (n) RETURN count(n) AS count").data()[0]["count"]
        rels_count = graph.run("MATCH ()-[r]->() RETURN count(r) AS count").data()[0]["count"]
        
        print(f"База данных содержит {nodes_count} узлов и {rels_count} связей")
        
        if not force:
            # Запрос подтверждения
            confirmation = input("ВНИМАНИЕ: Вы собираетесь удалить ВСЕ данные из базы Neo4j. Это необратимая операция.\nВведите 'yes' для подтверждения: ")
            if confirmation.lower() != 'yes':
                print("Операция отменена.")
                return False
        
        # Удаление всех узлов и связей
        print("Очистка базы данных...")
        result = graph.run("MATCH (n) DETACH DELETE n")
        
        # Проверка результата
        nodes_after = graph.run("MATCH (n) RETURN count(n) AS count").data()[0]["count"]
        rels_after = graph.run("MATCH ()-[r]->() RETURN count(r) AS count").data()[0]["count"]
        
        print(f"База данных успешно очищена. Удалено {nodes_count} узлов и {rels_count} связей.")
        print(f"Осталось {nodes_after} узлов и {rels_after} связей.")
        
        return True
    
    except Exception as e:
        print(f"Ошибка при очистке базы данных: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Полная очистка базы данных Neo4j")
    parser.add_argument("--force", action="store_true", help="Очистить без подтверждения (опасно)")
    args = parser.parse_args()
    
    clear_database(args.force)

if __name__ == "__main__":
    main()
