"""
SYNAPSE AI — Research Benchmark Dataset Model & Loader
======================================================
Defines the schema for research benchmark questions, expected evidence characteristics,
ground truth propositions, and reference corpus passages.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ReferencePassage:
    """A reference document passage with ground-truth relevance label."""
    doc_id: str
    url: str
    title: str
    domain: str
    source_type: str  # academic | official | news | industry | company | general
    publication_date: str
    text: str
    is_relevant: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "url": self.url,
            "title": self.title,
            "domain": self.domain,
            "source_type": self.source_type,
            "publication_date": self.publication_date,
            "text": self.text,
            "is_relevant": self.is_relevant,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReferencePassage":
        return cls(
            doc_id=data.get("doc_id", ""),
            url=data.get("url", ""),
            title=data.get("title", ""),
            domain=data.get("domain", ""),
            source_type=data.get("source_type", "general"),
            publication_date=data.get("publication_date", "N/A"),
            text=data.get("text", ""),
            is_relevant=bool(data.get("is_relevant", False)),
        )


@dataclass
class BenchmarkQuery:
    """A research question with expected evidence characteristics and ground truth."""
    id: str
    query: str
    category: str
    expected_entities: List[str]
    expected_domains: List[str]
    ground_truth_claims: List[str]
    unsupported_claims_to_test: List[str] = field(default_factory=list)
    reference_corpus: List[ReferencePassage] = field(default_factory=list)

    @property
    def relevant_doc_ids(self) -> List[str]:
        """IDs of passages labeled as relevant."""
        return [p.doc_id for p in self.reference_corpus if p.is_relevant]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "query": self.query,
            "category": self.category,
            "expected_entities": self.expected_entities,
            "expected_domains": self.expected_domains,
            "ground_truth_claims": self.ground_truth_claims,
            "unsupported_claims_to_test": self.unsupported_claims_to_test,
            "reference_corpus": [p.to_dict() for p in self.reference_corpus],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkQuery":
        passages = [ReferencePassage.from_dict(p) for p in data.get("reference_corpus", [])]
        return cls(
            id=data.get("id", ""),
            query=data.get("query", ""),
            category=data.get("category", "General"),
            expected_entities=data.get("expected_entities", []),
            expected_domains=data.get("expected_domains", []),
            ground_truth_claims=data.get("ground_truth_claims", []),
            unsupported_claims_to_test=data.get("unsupported_claims_to_test", []),
            reference_corpus=passages,
        )


@dataclass
class BenchmarkDataset:
    """Collection of research benchmark queries."""
    name: str
    version: str
    description: str
    queries: List[BenchmarkQuery] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.queries)

    def get_query(self, query_id: str) -> Optional[BenchmarkQuery]:
        for q in self.queries:
            if q.id == query_id:
                return q
        return None

    def filter_by_category(self, category: str) -> List[BenchmarkQuery]:
        return [q for q in self.queries if q.category.lower() == category.lower()]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "total_queries": len(self.queries),
            "queries": [q.to_dict() for q in self.queries],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkDataset":
        queries = [BenchmarkQuery.from_dict(q) for q in data.get("queries", [])]
        return cls(
            name=data.get("name", "SYNAPSE AI Benchmark"),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            queries=queries,
        )


def load_benchmark_dataset(path: str) -> BenchmarkDataset:
    """Load benchmark dataset from a JSON file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Benchmark dataset file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return BenchmarkDataset.from_dict(data)
