import re
import shutil
import uuid

import pymupdf4llm

from ._base import BaseParser


class PDFParser(BaseParser):
    def __init__(self):
        self._imgs_path = "_tmpimg_" + uuid.uuid4().hex
        self._remove_images_regex = re.compile(r"!\[\]\("+self._imgs_path+r"\/.*\)", re.UNICODE)
    
    def parse(self, filename: str, max_record_size: int = None):
        try:
            pages = pymupdf4llm.to_markdown(filename, ignore_code=True, page_chunks=True, show_progress=False, force_text=False, write_images=True, image_path=self._imgs_path, dpi=10)
        except Exception as e:
            raise ValueError(f"Error parsing PDF file: {e}")
        finally:
            # Remove unnecessarely created images
            shutil.rmtree(self._imgs_path)
        
        def _parse_text(text: str):
            # Remove images
            text = re.sub(self._remove_images_regex, "", text)
            
            return text.encode("utf-8")

        chunks = []
        if max_record_size:
            current_chunk_length = 0
            current_chunk = []
            for page in pages:
                page_content = _parse_text(page["text"])
                page_length = len(page_content)
                if page_length > max_record_size:
                    raise ValueError("Page content is too large to be uploaded.")
                if current_chunk_length + page_length > max_record_size:
                    chunks.append(b''.join((page for page in current_chunk)))
                    current_chunk = []
                    current_chunk_length = 0
                current_chunk.append(page_content)
                current_chunk_length += page_length
            chunks.append(b''.join((page for page in current_chunk)))
        else:
            chunks.append(b''.join((_parse_text(page["text"]) for page in pages)))

        return chunks
