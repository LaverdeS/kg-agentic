import os
import ssl
from dataclasses import dataclass
from pathlib import Path

import httpx
import truststore
from graphiti_core import Graphiti
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.driver.neo4j_driver import Neo4jDriver
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_client import OpenAIClient
from openai import AsyncOpenAI


@dataclass(frozen=True, slots=True)
class Settings:
    openai_api_key: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    neo4j_database: str
    model: str
    small_model: str
    embedding_model: str
    model_max_output_tokens: int
    graphiti_max_tokens: int
    graphiti_max_coroutines: int
    evidence_limit: int
    data_dir: Path

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            openai_api_key=_required("OPENAI_API_KEY"),
            neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
            neo4j_password=_required("NEO4J_PASSWORD"),
            neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
            model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
            small_model=os.getenv("OPENAI_SMALL_MODEL", "gpt-5-mini"),
            embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            model_max_output_tokens=_positive_int("MODEL_MAX_OUTPUT_TOKENS", 1200),
            graphiti_max_tokens=_positive_int("GRAPHITI_MAX_TOKENS", 4096),
            graphiti_max_coroutines=_positive_int("GRAPHITI_MAX_COROUTINES", 4),
            evidence_limit=_positive_int("INVESTIGATION_EVIDENCE_LIMIT", 8),
            data_dir=Path(os.getenv("KG_AGENTIC_DATA_DIR", "var/corpora")),
        )


@dataclass(slots=True)
class Runtime:
    graphiti: Graphiti
    openai: AsyncOpenAI

    async def close(self) -> None:
        await self.graphiti.close()
        await self.openai.close()


def build_runtime(settings: Settings) -> Runtime:
    ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    http_client = httpx.AsyncClient(verify=ssl_context)
    openai = AsyncOpenAI(api_key=settings.openai_api_key, http_client=http_client)
    llm_config = LLMConfig(
        api_key=settings.openai_api_key,
        model=settings.model,
        small_model=settings.small_model,
        max_tokens=settings.graphiti_max_tokens,
    )
    llm_client = OpenAIClient(
        config=llm_config,
        client=openai,
        max_tokens=settings.graphiti_max_tokens,
    )
    embedder = OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            embedding_model=settings.embedding_model,
            api_key=settings.openai_api_key,
        ),
        client=openai,
    )
    reranker = OpenAIRerankerClient(config=llm_config, client=llm_client)
    driver = Neo4jDriver(
        settings.neo4j_uri,
        settings.neo4j_user,
        settings.neo4j_password,
        database=settings.neo4j_database,
    )
    graphiti = Graphiti(
        graph_driver=driver,
        llm_client=llm_client,
        embedder=embedder,
        cross_encoder=reranker,
        store_raw_episode_content=True,
        max_coroutines=settings.graphiti_max_coroutines,
    )
    return Runtime(graphiti=graphiti, openai=openai)


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} must be set in the ignored .env file")
    return value


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value
