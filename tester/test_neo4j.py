import json
import os
from py2neo import Graph, Node, Relationship

# Конфигурация Neo4j
NEO4J_URI = "bolt://localhost:7687/system_self_development"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "neo4j"  # Рекомендуется сменить стандартный пароль

def test_neo4j_connection():
    """Проверка подключения к Neo4j"""
    try:
        graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        print("Подключение к Neo4j успешно!")
        
        # Простой запрос для проверки работы базы данных
        result = graph.run("MATCH (n) RETURN count(n) AS count").data()
        count = result[0]["count"] if result else 0
        print(f"Количество узлов в базе данных: {count}")
        
        return graph
    except Exception as e:
        print(f"Ошибка подключения к Neo4j: {str(e)}")
        return None

def load_first_chapter_to_neo4j(graph):
    """Загрузка данных анализа первой главы в Neo4j"""
    try:
        # Чтение JSON файла с анализом первой главы
        with open("first_chapter_analysis.json", "r", encoding="utf-8") as f:
            chapter_data = json.load(f)
        
        # Очистка базы данных перед загрузкой
        print("Очистка базы данных...")
        graph.run("MATCH (n) DETACH DELETE n")
        
        # Создание узла главы
        chapter_node = Node("Chapter", 
                          name="Глава 1: Физический мир и ментальное пространство",
                          main_ideas=chapter_data.get("main_ideas", []))
        graph.create(chapter_node)
        print("Создан узел главы")
        
        # Словарь для отслеживания созданных узлов понятий
        concepts = {}
        
        # Создание узлов понятий
        for concept in chapter_data.get("concepts", []):
            concept_name = concept["name"]
            
            concept_node = Node("Concept",
                              name=concept_name,
                              definition=concept.get("definition", ""),
                              example=concept.get("example", ""),
                              questions=concept.get("questions", []))
            graph.create(concept_node)
            concepts[concept_name] = concept_node
            print(f"Создан узел понятия: {concept_name}")
            
            # Создаем связь PART_OF между понятием и главой
            rel = Relationship(concept_node, "PART_OF", chapter_node,
                              description=f"Понятие '{concept_name}' является частью Главы 1")
            graph.create(rel)
        
        # Создание связей между понятиями
        for rel_data in chapter_data.get("relationships", []):
            source_name = rel_data["source"]
            target_name = rel_data["target"]
            rel_type = rel_data["type"]
            description = rel_data.get("description", "")
            
            # Проверяем, есть ли указанные понятия в словаре
            if source_name in concepts and target_name in concepts:
                rel = Relationship(concepts[source_name], rel_type, concepts[target_name],
                                  description=description)
                graph.create(rel)
                print(f"Создана связь {rel_type} между {source_name} и {target_name}")
            else:
                print(f"Пропущена связь {rel_type} между {source_name} и {target_name} (одно из понятий не найдено)")
        
        # Проверка созданных данных
        node_count = graph.run("MATCH (n) RETURN count(n) AS count").data()[0]["count"]
        rel_count = graph.run("MATCH ()-[r]->() RETURN count(r) AS count").data()[0]["count"]
        
        print(f"Загрузка завершена. Создано {node_count} узлов и {rel_count} связей")
        return True
    except Exception as e:
        print(f"Ошибка при загрузке данных в Neo4j: {str(e)}")
        return False

def main():
    print("Тестирование Neo4j...")
    
    # Проверка подключения
    graph = test_neo4j_connection()
    if not graph:
        return
    
    # Загрузка данных
    success = load_first_chapter_to_neo4j(graph)
    
    if success:
        print("Данные успешно загружены в Neo4j")
        
        # Выполнение тестового запроса
        print("\nПроверка загруженных данных...")
        
        # Получение всех понятий
        concepts = graph.run("""
            MATCH (c:Concept) 
            RETURN c.name AS name, c.definition AS definition
        """).data()
        
        print(f"Количество загруженных понятий: {len(concepts)}")
        for i, concept in enumerate(concepts):
            print(f"{i+1}. {concept['name']}: {concept['definition'][:100]}...")
        
        # Получение всех отношений
        relationships = graph.run("""
            MATCH (c1:Concept)-[r]->(c2:Concept)
            RETURN c1.name AS source, type(r) AS type, c2.name AS target, r.description AS description
        """).data()
        
        print(f"\nКоличество загруженных отношений между понятиями: {len(relationships)}")
        for i, rel in enumerate(relationships):
            print(f"{i+1}. {rel['source']} -{rel['type']}-> {rel['target']}")
    else:
        print("Не удалось загрузить данные в Neo4j")

if __name__ == "__main__":
    main() 