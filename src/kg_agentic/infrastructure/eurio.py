import json
import ssl
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx
import truststore

from kg_agentic.knowledge.models import EvidenceKind, Relationship, SourceDocument, StructuralPath

EURIO = "http://data.europa.eu/s66#"
EURIO_PROJECT_PREFIX = "http://data.europa.eu/s66/resource/projects/"
DEFAULT_SPARQL_ENDPOINT = "https://cordis.europa.eu/datalab/sparql-api"


class SparqlQueryClient(Protocol):
    async def query(self, sparql: str) -> dict[str, Any]: ...


class HttpSparqlQueryClient:
    def __init__(
        self,
        endpoint: str = DEFAULT_SPARQL_ENDPOINT,
        *,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.endpoint = endpoint
        self._timeout_seconds = timeout_seconds

    async def query(self, sparql: str) -> dict[str, Any]:
        ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        async with httpx.AsyncClient(
            timeout=self._timeout_seconds,
            follow_redirects=True,
            verify=ssl_context,
        ) as client:
            response = await client.get(
                self.endpoint,
                params={"query": sparql, "format": "application/sparql-results+json"},
                headers={"Accept": "application/sparql-results+json"},
            )
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("EURIO returned a non-object SPARQL response")
        return payload


class EurioStructuralSource:
    """Map official EURIO bindings to bounded typed, directed paths."""

    def __init__(
        self,
        query_client: SparqlQueryClient,
        *,
        source_url: str = DEFAULT_SPARQL_ENDPOINT,
    ) -> None:
        self._query_client = query_client
        self._source_url = source_url

    async def find_paths(self, *, project_iris: tuple[str, ...]) -> tuple[StructuralPath, ...]:
        values = _project_values(project_iris)
        roles_response = await self._query_client.query(_roles_query(values))
        results_response = await self._query_client.query(_results_query(values))
        roles_by_project = _bindings_by_project(roles_response)
        results_by_project = _bindings_by_project(results_response)

        paths: list[StructuralPath] = []
        for project in project_iris:
            roles = roles_by_project.get(project, ())
            results = results_by_project.get(project, ())
            if not roles or not results:
                continue
            role = roles[0]
            result = results[0]
            role_iri = _value(role, "role")
            organisation_iri = _value(role, "organisation")
            result_iri = _value(result, "result")
            if not role_iri or not organisation_iri or not result_iri:
                continue
            role_label = _value(role, "roleLabel")
            role_attributes = (("roleLabel", role_label),) if role_label else ()
            paths.append(
                StructuralPath(
                    relationships=(
                        Relationship(
                            subject=project,
                            predicate=f"{EURIO}hasInvolvedParty",
                            object=role_iri,
                            source_url=self._source_url,
                            attributes=role_attributes,
                        ),
                        Relationship(
                            subject=role_iri,
                            predicate=f"{EURIO}isRoleOf",
                            object=organisation_iri,
                            source_url=self._source_url,
                            attributes=role_attributes,
                        ),
                        Relationship(
                            subject=project,
                            predicate=f"{EURIO}hasResult",
                            object=result_iri,
                            source_url=self._source_url,
                        ),
                    )
                )
            )
        return tuple(paths)


class EurioEvidenceSource:
    """Fetch a bounded current evidence corpus without upgrading metadata to full text."""

    def __init__(self, query_client: SparqlQueryClient, *, corpus_id: str) -> None:
        self._query_client = query_client
        self._corpus_id = corpus_id

    async def fetch_documents(
        self,
        *,
        project_iris: tuple[str, ...],
        results_per_project: int = 2,
    ) -> tuple[SourceDocument, ...]:
        if results_per_project < 0:
            raise ValueError("results_per_project cannot be negative")
        values = _project_values(project_iris)
        retrieved_at = datetime.now(UTC)
        records_response = await self._query_client.query(_project_records_query(values))
        results_response = await self._query_client.query(_result_metadata_query(values))
        documents = _project_documents(
            records_response,
            corpus_id=self._corpus_id,
            retrieved_at=retrieved_at,
        )
        documents.extend(
            _result_documents(
                results_response,
                corpus_id=self._corpus_id,
                retrieved_at=retrieved_at,
                per_project=results_per_project,
            )
        )
        return tuple(documents)


def _project_values(project_iris: tuple[str, ...]) -> str:
    if not project_iris:
        raise ValueError("At least one EURIO project IRI is required")
    for iri in project_iris:
        suffix = iri.removeprefix(EURIO_PROJECT_PREFIX)
        if not suffix or iri != f"{EURIO_PROJECT_PREFIX}{suffix}":
            raise ValueError(f"Not a canonical EURIO project IRI: {iri}")
        if any(character not in "0123456789abcdef-" for character in suffix.lower()):
            raise ValueError(f"Unsafe EURIO project IRI: {iri}")
    return " ".join(f"<{iri}>" for iri in project_iris)


def _roles_query(values: str) -> str:
    return f"""PREFIX eurio: <{EURIO}>
SELECT DISTINCT ?project ?role ?roleLabel ?organisation
WHERE {{
  VALUES ?project {{ {values} }}
  ?project eurio:hasInvolvedParty ?role .
  ?role eurio:isRoleOf ?organisation .
  OPTIONAL {{ ?role eurio:roleLabel ?roleLabel }}
}}
ORDER BY ?project ?organisation ?role
"""


def _results_query(values: str) -> str:
    return f"""PREFIX eurio: <{EURIO}>
SELECT DISTINCT ?project ?result
WHERE {{
  VALUES ?project {{ {values} }}
  ?project eurio:hasResult ?result .
}}
ORDER BY ?project ?result
"""


def _project_records_query(values: str) -> str:
    return f"""PREFIX eurio: <{EURIO}>
SELECT DISTINCT ?project ?id ?title ?abstract ?startDate ?endDate ?status
WHERE {{
  VALUES ?project {{ {values} }}
  ?project eurio:identifier ?id; eurio:title ?title; eurio:abstract ?abstract .
  OPTIONAL {{ ?project eurio:startDate ?startDate }}
  OPTIONAL {{ ?project eurio:endDate ?endDate }}
  OPTIONAL {{ ?project eurio:projectStatus ?status }}
}}
ORDER BY ?project
"""


def _result_metadata_query(values: str) -> str:
    return f"""PREFIX eurio: <{EURIO}>
SELECT DISTINCT ?project ?result ?type ?title ?doi
WHERE {{
  VALUES ?project {{ {values} }}
  ?project eurio:hasResult ?result .
  ?result a ?type .
  OPTIONAL {{ ?result eurio:title ?title }}
  OPTIONAL {{ ?result eurio:doi ?doi }}
}}
ORDER BY ?project ?result ?type
"""


def _bindings_by_project(response: dict[str, Any]) -> dict[str, tuple[dict[str, Any], ...]]:
    raw_bindings = response.get("results", {}).get("bindings", [])
    if not isinstance(raw_bindings, list):
        raise ValueError("Invalid SPARQL bindings payload")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for binding in raw_bindings:
        if not isinstance(binding, dict):
            continue
        project = _value(binding, "project")
        if project:
            grouped[project].append(binding)
    return {project: tuple(bindings) for project, bindings in grouped.items()}


def _value(binding: dict[str, Any], name: str) -> str | None:
    cell = binding.get(name)
    if not isinstance(cell, dict):
        return None
    value = cell.get("value")
    return value if isinstance(value, str) else None


def _project_documents(
    response: dict[str, Any], *, corpus_id: str, retrieved_at: datetime
) -> list[SourceDocument]:
    documents: list[SourceDocument] = []
    for binding in _raw_bindings(response):
        project = _value(binding, "project")
        identifier = _value(binding, "id")
        title = _value(binding, "title")
        abstract = _value(binding, "abstract")
        if not all((project, identifier, title, abstract)):
            continue
        status = _value(binding, "status") or "unknown"
        passage = str(abstract)
        documents.append(
            SourceDocument(
                dataset_id="cordis-eurio",
                corpus_id=corpus_id,
                source_id=f"project-{identifier}",
                source_url=f"https://cordis.europa.eu/project/id/{identifier}",
                source_category="project_record",
                text=(
                    f"CORDIS project record for {title} (status: {status}). "
                    "The following is a source-reported objective, not proof of achievement: "
                    f"{passage}"
                ),
                passage=passage,
                kind=EvidenceKind.SOURCE_CLAIM,
                canonical_entity_iris=(str(project),),
                publication_at=None,
                update_at=None,
                event_at=_parse_date(_value(binding, "startDate")),
                retrieved_at=retrieved_at,
                raw_payload=_binding_bytes(binding),
            )
        )
    return documents


def _result_documents(
    response: dict[str, Any],
    *,
    corpus_id: str,
    retrieved_at: datetime,
    per_project: int,
) -> list[SourceDocument]:
    counts: dict[str, int] = defaultdict(int)
    seen: set[tuple[str, str]] = set()
    documents: list[SourceDocument] = []
    for binding in _raw_bindings(response):
        project = _value(binding, "project")
        result = _value(binding, "result")
        if not project or not result or (project, result) in seen:
            continue
        if counts[project] >= per_project:
            continue
        seen.add((project, result))
        counts[project] += 1
        result_id = result.rsplit("/", 1)[-1]
        title = _value(binding, "title") or result_id
        doi = _value(binding, "doi")
        description = f"Metadata-only EURIO result record: {title}."
        if doi:
            description += f" DOI: {doi}."
        description += " No full-text content was retrieved from this binding."
        documents.append(
            SourceDocument(
                dataset_id="cordis-eurio",
                corpus_id=corpus_id,
                source_id=f"result-{result_id}",
                source_url=result,
                source_category="result_metadata",
                text=description,
                passage=title,
                kind=EvidenceKind.STRUCTURED_FACT,
                canonical_entity_iris=(project, result),
                publication_at=None,
                update_at=None,
                event_at=None,
                retrieved_at=retrieved_at,
                raw_payload=_binding_bytes(binding),
            )
        )
    return documents


def _raw_bindings(response: dict[str, Any]) -> list[dict[str, Any]]:
    raw_bindings = response.get("results", {}).get("bindings", [])
    if not isinstance(raw_bindings, list):
        raise ValueError("Invalid SPARQL bindings payload")
    return [binding for binding in raw_bindings if isinstance(binding, dict)]


def _binding_bytes(binding: dict[str, Any]) -> bytes:
    return json.dumps(binding, ensure_ascii=False, sort_keys=True).encode("utf-8")


def _parse_date(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"Invalid EURIO date: {value}") from error
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed
