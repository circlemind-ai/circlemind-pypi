import unittest
from unittest.mock import MagicMock
import re

class TestFormatReferences(unittest.TestCase):
    def setUp(self):
        self.obj = MagicMock()
        self.obj.response = "lorem ipsum doloret sit amen[1][2]. Que avoc cause post para bellum sic lupus [3][1]"
        self.obj.context = {
            "chunks": {
                "1": {"full_doc_id": "doc1"},
                "2": {"full_doc_id": "doc2"},
                "3": {"full_doc_id": "doc3"}
            },
            "documents": {
                "doc1": {"metadata": "URL1"},
                "doc2": {"metadata": "URL2"},
                "doc3": {"metadata": "URL3"}
            }
        }

    def test_format_references_default_format_fn(self):
        def format_references(self, format_fn=None):
            doc_id_to_index = {}
            def _replace_fn(match):
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
                format_fn = lambda i, _: f"[{i}]"  # noqa: E731
            return re.sub(r'\[\d[\s\d\]\[]*\]', _replace_fn, self.response), {i: self.context["documents"][doc_id]["metadata"] for doc_id, i in doc_id_to_index.items()}
        
        self.obj.format_references = format_references.__get__(self.obj)
        formatted_response, metadata = self.obj.format_references()
        self.assertEqual(formatted_response, "lorem ipsum doloret sit amen[1][2]. Que avoc cause post para bellum sic lupus [3][1]")
        self.assertEqual(metadata, {1: "URL1", 2: "URL2", 3: "URL3"})

    def test_format_references_custom_format_fn(self):
        def custom_format_fn(index, metadata):
            return f"({index}: {metadata})"
        
        def format_references(self, format_fn=None):
            doc_id_to_index = {}
            def _replace_fn(match):
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
                format_fn = lambda i, _: f"[{i}]"  # noqa: E731
            return re.sub(r'\[\d[\s\d\]\[]*\]', _replace_fn, self.response), {i: self.context["documents"][doc_id]["metadata"] for doc_id, i in doc_id_to_index.items()}
        
        self.obj.format_references = format_references.__get__(self.obj)
        formatted_response, metadata = self.obj.format_references(custom_format_fn)
        self.assertEqual(formatted_response, "lorem ipsum doloret sit amen(1: URL1)(2: URL2). Que avoc cause post para bellum sic lupus (3: URL3)(1: URL1)")
        self.assertEqual(metadata, {1: "URL1", 2: "URL2", 3: "URL3"})

if __name__ == '__main__':
    unittest.main()