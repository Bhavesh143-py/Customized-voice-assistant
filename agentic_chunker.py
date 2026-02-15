from langchain_core.prompts import ChatPromptTemplate
import uuid
from langchain_community.chat_models import ChatOllama
from typing import Optional
from pydantic import BaseModel
from rich import print

# -------- NEW IMPORTS --------
import json
import os
# -----------------------------


class AgenticChunker:
    def __init__(self):
        self.chunks = {}
        self.id_truncate_limit = 5

        self.generate_new_metadata_ind = True
        self.print_logging = True

        # ---- LLM via Ollama ----
        self.llm = ChatOllama(
            model="qwen2.5:3b",
            temperature=0
        )

    # ============================================================
    # ---------------- PERSISTENCE METHODS ----------------
    # ============================================================

    def save_chunks(self, path="agentic_chunks.json"):
        """Save chunks to disk"""

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.chunks, f, indent=2, ensure_ascii=False)

        if self.print_logging:
            print(f"\nSaved {len(self.chunks)} chunks → {path}")

    def load_chunks(self, path="agentic_chunks.json"):
        """Load chunks from disk"""

        if not os.path.exists(path):
            print("No saved chunks found")
            return

        with open(path, "r", encoding="utf-8") as f:
            self.chunks = json.load(f)

        if self.print_logging:
            print(f"\nLoaded {len(self.chunks)} chunks ← {path}")

    # ============================================================
    # Public Methods
    # ============================================================

    def add_propositions(self, propositions):
        for proposition in propositions:
            self.add_proposition(proposition)

    def add_proposition(self, proposition):
        if self.print_logging:
            print(f"\nAdding: '{proposition}'")

        if len(self.chunks) == 0:
            if self.print_logging:
                print("No chunks, creating a new one")
            self._create_new_chunk(proposition)
            return

        chunk_id = self._find_relevant_chunk(proposition)

        if chunk_id:
            if self.print_logging:
                print(
                    f"Chunk Found ({self.chunks[chunk_id]['chunk_id']}), "
                    f"adding to: {self.chunks[chunk_id]['title']}"
                )
            self.add_proposition_to_chunk(chunk_id, proposition)
        else:
            if self.print_logging:
                print("No chunks found")
            self._create_new_chunk(proposition)

    # ============================================================
    # Chunk Updates
    # ============================================================

    def add_proposition_to_chunk(self, chunk_id, proposition):
        self.chunks[chunk_id]["propositions"].append(proposition)

        if self.generate_new_metadata_ind:
            self.chunks[chunk_id]["summary"] = \
                self._update_chunk_summary(self.chunks[chunk_id])

            self.chunks[chunk_id]["title"] = \
                self._update_chunk_title(self.chunks[chunk_id])

    # ============================================================
    # Summary / Title Updates
    # ============================================================

    def _update_chunk_summary(self, chunk):
        PROMPT = ChatPromptTemplate.from_messages(
            [
                ("system", "..."),
                ("user",
                 "Chunk's propositions:\n{proposition}\n\n"
                 "Current chunk summary:\n{current_summary}")
            ]
        )

        runnable = PROMPT | self.llm

        return runnable.invoke({
            "proposition": "\n".join(chunk["propositions"]),
            "current_summary": chunk["summary"]
        }).content

    def _update_chunk_title(self, chunk):
        PROMPT = ChatPromptTemplate.from_messages(
            [
                ("system", "..."),
                ("user",
                 "Chunk's propositions:\n{proposition}\n\n"
                 "Chunk summary:\n{current_summary}\n\n"
                 "Current chunk title:\n{current_title}")
            ]
        )

        runnable = PROMPT | self.llm

        return runnable.invoke({
            "proposition": "\n".join(chunk["propositions"]),
            "current_summary": chunk["summary"],
            "current_title": chunk["title"]
        }).content

    # ============================================================
    # New Chunk Creation
    # ============================================================

    def _get_new_chunk_summary(self, proposition):
        PROMPT = ChatPromptTemplate.from_messages(
            [
                ("system", "..."),
                ("user",
                 "Determine the summary of the new chunk "
                 "that this proposition will go into:\n{proposition}")
            ]
        )

        runnable = PROMPT | self.llm

        return runnable.invoke({
            "proposition": proposition
        }).content

    def _get_new_chunk_title(self, summary):
        PROMPT = ChatPromptTemplate.from_messages(
            [
                ("system", "..."),
                ("user",
                 "Determine the title of the chunk that this "
                 "summary belongs to:\n{summary}")
            ]
        )

        runnable = PROMPT | self.llm

        return runnable.invoke({
            "summary": summary
        }).content

    def _create_new_chunk(self, proposition):
        new_chunk_id = str(uuid.uuid4())[:self.id_truncate_limit]

        new_chunk_summary = \
            self._get_new_chunk_summary(proposition)

        new_chunk_title = \
            self._get_new_chunk_title(new_chunk_summary)

        self.chunks[new_chunk_id] = {
            "chunk_id": new_chunk_id,
            "propositions": [proposition],
            "title": new_chunk_title,
            "summary": new_chunk_summary,
            "chunk_index": len(self.chunks)
        }

        if self.print_logging:
            print(f"Created new chunk ({new_chunk_id}): {new_chunk_title}")

    # ============================================================
    # Retrieval Helpers
    # ============================================================

    def get_chunk_outline(self):
        chunk_outline = ""

        for chunk_id, chunk in self.chunks.items():
            chunk_outline += (
                f"Chunk ({chunk['chunk_id']}): {chunk['title']}\n"
                f"Summary: {chunk['summary']}\n\n"
            )

        return chunk_outline

    def _find_relevant_chunk(self, proposition):
        current_chunk_outline = self.get_chunk_outline()

        PROMPT = ChatPromptTemplate.from_messages(
            [
                ("system", "..."),
                ("user",
                 "Current Chunks:\n--Start--\n"
                 "{current_chunk_outline}\n--End--"),
                ("user",
                 "Determine if the following statement "
                 "should belong:\n{proposition}")
            ]
        )

        runnable = PROMPT | self.llm

        chunk_found = runnable.invoke({
            "proposition": proposition,
            "current_chunk_outline": current_chunk_outline
        }).content

        chunk_found = chunk_found.strip()

        if not chunk_found or \
           len(chunk_found) != self.id_truncate_limit:
            return None

        return chunk_found

    # ============================================================
    # Getters / Printers
    # ============================================================

    def get_chunks(self, get_type="dict"):
        if get_type == "dict":
            return self.chunks

        if get_type == "list_of_strings":
            return [
                " ".join(chunk["propositions"])
                for chunk in self.chunks.values()
            ]

    def pretty_print_chunks(self):
        print(f"\nYou have {len(self.chunks)} chunks\n")

        for chunk_id, chunk in self.chunks.items():
            print(f"Chunk #{chunk['chunk_index']}")
            print(f"Chunk ID: {chunk_id}")
            print(f"Summary: {chunk['summary']}")
            print("Propositions:")
            for prop in chunk["propositions"]:
                print(f"  - {prop}")
            print("\n")
