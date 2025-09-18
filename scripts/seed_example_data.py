"""Script to seed additional example data for testing."""

import json
import os
from pathlib import Path


def append_qa_pair(query: str, answer: str, qa_file: str = "data/golden/qaset.jsonl"):
    """
    Append a new QA pair to the dataset.
    
    Args:
        query: Question string
        answer: Expected answer string
        qa_file: Path to QA dataset file
    """
    qa_item = {
        "query": query,
        "answer": answer
    }
    
    # Ensure directory exists
    Path(qa_file).parent.mkdir(parents=True, exist_ok=True)
    
    # Append to file
    with open(qa_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(qa_item) + '\n')
    
    print(f"Added QA pair to {qa_file}")
    print(f"Query: {query}")
    print(f"Answer: {answer[:100]}...")


def append_passage(passage_id: str, text: str, passages_file: str = "data/golden/passages.jsonl"):
    """
    Append a new passage to the dataset.
    
    Args:
        passage_id: Unique identifier for the passage
        text: Passage text content
        passages_file: Path to passages dataset file
    """
    passage_item = {
        "id": passage_id,
        "text": text
    }
    
    # Ensure directory exists
    Path(passages_file).parent.mkdir(parents=True, exist_ok=True)
    
    # Append to file
    with open(passages_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(passage_item) + '\n')
    
    print(f"Added passage to {passages_file}")
    print(f"ID: {passage_id}")
    print(f"Text: {text[:100]}...")


def seed_data_engineering_examples():
    """Seed additional data engineering examples."""
    
    # Additional QA pairs
    qa_examples = [
        {
            "query": "What is the difference between ETL and ELT?",
            "answer": "ETL (Extract, Transform, Load) processes data transformation before loading into the target system, while ELT (Extract, Load, Transform) loads raw data first and transforms it within the target system. ELT is often preferred for cloud data warehouses with powerful compute capabilities, while ETL is better for systems with limited processing power or when data needs significant cleaning before storage."
        },
        {
            "query": "How can I implement data versioning in my pipeline?",
            "answer": "Data versioning can be implemented using several approaches: timestamp-based versioning (adding processing timestamps), hash-based versioning (using content hashes), semantic versioning (major.minor.patch), or using specialized tools like DVC (Data Version Control), Delta Lake, or Apache Iceberg. Choose based on your use case - timestamps for audit trails, hashes for change detection, and semantic versioning for controlled releases."
        }
    ]
    
    # Additional passages
    passage_examples = [
        {
            "id": "passage_4",
            "text": "Data pipeline orchestration tools like Apache Airflow, Prefect, and Dagster help manage complex data workflows. These tools provide scheduling, dependency management, monitoring, and retry mechanisms. Key features include DAG (Directed Acyclic Graph) visualization, task parallelization, failure handling, and integration with various data sources and destinations. When choosing an orchestration tool, consider factors like ease of use, scalability, community support, and integration capabilities with your existing tech stack."
        },
        {
            "id": "passage_5",
            "text": "Data warehouse design patterns include star schema, snowflake schema, and data vault modeling. Star schema is simple with a central fact table surrounded by dimension tables. Snowflake schema normalizes dimension tables to reduce redundancy but increases query complexity. Data vault 2.0 provides flexibility and auditability with hub, link, and satellite tables. Choose based on query patterns, data volume, change frequency, and team expertise. Modern cloud warehouses often favor dimensional modeling for analytical workloads."
        }
    ]
    
    # Add examples
    print("Seeding additional data engineering examples...")
    
    for qa in qa_examples:
        append_qa_pair(qa["query"], qa["answer"])
    
    for passage in passage_examples:
        append_passage(passage["id"], passage["text"])
    
    print("Seeding completed!")


def seed_ml_ops_examples():
    """Seed ML operations examples."""
    
    qa_examples = [
        {
            "query": "What are the key components of MLOps?",
            "answer": "Key MLOps components include version control for data and models, automated training pipelines, model validation and testing, deployment automation, monitoring and observability, feature stores, experiment tracking, and model governance. These components enable reliable, scalable, and reproducible machine learning workflows in production environments."
        }
    ]
    
    passage_examples = [
        {
            "id": "passage_6",
            "text": "Model monitoring in production involves tracking data drift, model performance degradation, and prediction quality over time. Key metrics include accuracy, precision, recall, latency, throughput, and business-specific KPIs. Drift detection compares current data distributions with training data using statistical tests or ML-based approaches. Alert systems should trigger retraining when performance drops below thresholds or significant drift is detected."
        }
    ]
    
    print("Seeding MLOps examples...")
    
    for qa in qa_examples:
        append_qa_pair(qa["query"], qa["answer"])
    
    for passage in passage_examples:
        append_passage(passage["id"], passage["text"])
    
    print("MLOps seeding completed!")


def main():
    """Main function with CLI interface."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Seed example data for AI Quality Kit")
    parser.add_argument(
        "--type", 
        choices=["data-eng", "mlops", "custom"], 
        default="data-eng",
        help="Type of examples to seed"
    )
    parser.add_argument(
        "--qa-query", 
        help="Custom QA query (requires --qa-answer)"
    )
    parser.add_argument(
        "--qa-answer", 
        help="Custom QA answer (requires --qa-query)"
    )
    parser.add_argument(
        "--passage-id", 
        help="Custom passage ID (requires --passage-text)"
    )
    parser.add_argument(
        "--passage-text", 
        help="Custom passage text (requires --passage-id)"
    )
    
    args = parser.parse_args()
    
    if args.type == "data-eng":
        seed_data_engineering_examples()
    elif args.type == "mlops":
        seed_ml_ops_examples()
    elif args.type == "custom":
        if args.qa_query and args.qa_answer:
            append_qa_pair(args.qa_query, args.qa_answer)
        
        if args.passage_id and args.passage_text:
            append_passage(args.passage_id, args.passage_text)
        
        if not any([args.qa_query, args.passage_id]):
            print("For custom type, provide --qa-query + --qa-answer and/or --passage-id + --passage-text")
    
    print(f"\nTo rebuild the RAG index with new data, restart your FastAPI service or run:")
    print("python -c 'from apps.rag_service.rag_pipeline import RAGPipeline; rag = RAGPipeline(\"gpt-4o-mini\", 4); rag.build_index_from_passages(\"data/golden/passages.jsonl\")'")


if __name__ == "__main__":
    main()