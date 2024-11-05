from dataclasses import dataclass, field
import time
import json
from typing import Any, Optional, Union, Callable, Dict, Sequence, Tuple, List
from pathlib import Path
import re
import os

import circlemind_sdk
from circlemind_sdk.httpclient import AsyncHttpClient, HttpClient
from circlemind_sdk.utils.logger import Logger
from circlemind_sdk.utils.retries import RetryConfig
from circlemind_sdk.types import OptionalNullable, UNSET

from circlemind._parser import PDFParser


MAX_DB_ENTRY = 1024 * 256


# Custom Exceptions
class CirclemindError(Exception):
    """Base class for exceptions in the Circlemind SDK."""
    pass


@dataclass
class CirclemindQueryResponse:
    response: str = field()
    context: Dict[str, Any] = field()
    
    def format_references(self, format_fn: Optional[Callable[[Any, int], str]] = None) -> str:
        doc_id_to_index: Dict[str, int] = {}
        def _replace_fn(match: str) -> str:
            text = match.group()
            references = re.findall(r'(\d)', text)
            seen_docs = set()
            
            r = ""
            for reference in references:
                if reference not in self.context["chunks"]:
                    continue
                doc_id = self.context["chunks"][reference]["full_doc_id"]
                if doc_id in seen_docs or doc_id not in self.context["documents"]:
                    continue
                seen_docs.add(doc_id)
                
                if doc_id not in doc_id_to_index:
                    doc_id_to_index[doc_id] = len(doc_id_to_index) + 1
                
                doc = self.context["documents"][doc_id]
                r += format_fn(doc_id_to_index[doc_id], doc["metadata"])
            return r
        
        if format_fn is None:
            format_fn = lambda i, _: f"[{i}]"
        return re.sub(r'\[\d[\s\d\]\[]*\]', _replace_fn, self.response), {i: self.context["documents"][doc_id]["metadata"] for doc_id, i in doc_id_to_index.items()}


# Circlemind SDK Client
class Circlemind:
    def __init__(self, api_key: Optional[
            Union[Optional[str], Callable[[], Optional[str]]]
        ] = None,
        server_idx: Optional[int] = None,
        server_url: Optional[str] = None,
        url_params: Optional[Dict[str, str]] = None,
        client: Optional[HttpClient] = None,
        async_client: Optional[AsyncHttpClient] = None,
        retry_config: OptionalNullable[RetryConfig] = UNSET,
        timeout_ms: Optional[int] = None,
        debug_logger: Optional[Logger] = None
    ):
        if api_key is None:
            api_key = os.environ.get("CIRCLEMIND_API_KEY", None)
        self._sdk = circlemind_sdk.CirclemindSDK(
            api_key_header=api_key,
            server_idx=server_idx,
            server_url=server_url,
            url_params=url_params,
            client=client,
            async_client=async_client,
            retry_config=retry_config,
            timeout_ms=timeout_ms,
            debug_logger=debug_logger
        )

    def list_graphs(
        self,
    ) -> Sequence[str]:
        return self._sdk.list_graphs()["graphs"]
    
    def create_graph(
        self,
        graph_id: str,
        domain: str,
        example_queries: Sequence[str] | str,
        entity_types: Sequence[str],
    ) -> str:
        if isinstance(example_queries, str):
            example_queries = [example_queries]

        return self._sdk.create_graph(
            graph_id=graph_id,
            configure_request={
                "domain": domain,
                "example_queries": "\n".join(example_queries),
                "entity_types": entity_types
            }
        )
        
    def configure(
        self,
        graph_id: str,
        domain: str,
        example_queries: Sequence[str] | str,
        entity_types: Sequence[str],
    ) -> str:
        if isinstance(example_queries, str):
            example_queries = [example_queries]

        return self._sdk.configure(
            graph_id=graph_id,
            configure_request={
                "domain": domain,
                "example_queries": "\n".join(example_queries),
                "entity_types": entity_types
            })
    
    def add(
        self,
        memory: Union[str, Path],
        graph_id: str = "default",
        metadata: Optional[Dict[str, str]] = None
    ):
        if isinstance(memory, Path):
            if memory.suffix == ".pdf":
                parser = PDFParser()
                memories = parser.parse(memory, max_record_size=MAX_DB_ENTRY)
                for memory in memories:
                    self._sdk.add(
                        graph_id=graph_id,
                        memory_request={
                            "memory": memory, "metadata": json.dumps(metadata)
                        })
            else:
                raise CirclemindError("Only PDF files are supported for now.")
        else:
            if len(memory) > MAX_DB_ENTRY:
                memories = [memory[i:i+MAX_DB_ENTRY] for i in range(0, len(memory), MAX_DB_ENTRY)]
            else:
                memories = [memory]
            
            for memory in memories:
                self._sdk.add(
                    graph_id=graph_id,
                    memory_request={
                        "memory": memory, "metadata": json.dumps(metadata)
                    })

        return
    
    def query(
        self,
        query: str,
        graph_id: str = "default",
        with_references: Optional[bool] = False
    ) -> Union[Tuple[str, List[str]], str, List[str]]:
        status = None
        query_response = self._sdk.query(
            graph_id=graph_id,
            reasoning_request={
                "query": query,
                "parameters": json.dumps({"with_references": with_references})
        })
        
        while status is None or status not in ["DONE", "FAILED", "dev_DONE", "dev_FAILED"]:
            reasoning_response = self._sdk.get_reasoning(
                graph_id=graph_id,
                request_id=query_response.request_id,
                request_time=query_response.request_time
            )
            status = reasoning_response.status
            time.sleep(0.5)
        
        try:
            return CirclemindQueryResponse(reasoning_response.memories, json.loads(reasoning_response.context))

        except json.JSONDecodeError:
            raise CirclemindError("This is a bug, contact support@circlemind.co.")
