"""The in-memory knowledge base the server queries.

A single ``Knowledge`` object is produced either by *live* extraction from a
HICAR checkout (``extract.runner``) or by loading *bundled* artifacts
(``artifacts.loader``). The server depends only on this interface, so the two
modes are interchangeable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .knowledge.namelist_schema import NamelistSchema
from .knowledge.schemes import categories as _categories
from .models import ModelVar, NmlOption, Scheme


@dataclass
class DocPage:
    name: str
    title: str
    text: str
    order: int = 0


@dataclass
class Knowledge:
    schema: NamelistSchema
    schemes: list[Scheme]
    variables: list[ModelVar]
    kvars: list[str]
    docs: dict[str, DocPage]
    examples: dict[str, str]
    version: dict          # version.json content
    mode: str = "bundled"  # "live" | "bundled"

    # internal index built lazily
    _var_by_name: dict[str, ModelVar] | None = field(default=None, repr=False)

    # ---- namelist options ----
    def get_option(self, name: str) -> NmlOption | None:
        return self.schema.get(name)

    def search_options(self, query: str, group: str | None = None) -> list[NmlOption]:
        return self.schema.search(query, group)

    def list_groups(self) -> list[str]:
        return self.schema.groups

    def options_in_group(self, group: str) -> list[NmlOption]:
        return self.schema.options_in_group(group)

    # ---- schemes ----
    def scheme_categories(self) -> list[str]:
        return _categories(self.schemes)

    def schemes_for(self, category: str) -> list[Scheme]:
        c = category.lower()
        return [s for s in self.schemes if s.category == c or s.selector == c]

    def resolve_scheme(self, category: str, value: str) -> Scheme | None:
        v = str(value).strip().lower()
        for s in self.schemes_for(category):
            if (s.name and s.name.lower() == v) or (s.code is not None and str(s.code) == v):
                return s
        return None

    # ---- variables ----
    def _ensure_var_index(self) -> dict[str, ModelVar]:
        if self._var_by_name is None:
            idx: dict[str, ModelVar] = {}
            for v in self.variables:
                idx.setdefault(v.name.lower(), v)
                idx.setdefault(v.kvar.lower(), v)
            self._var_by_name = idx
        return self._var_by_name

    def get_variable(self, name: str) -> ModelVar | None:
        return self._ensure_var_index().get(name.lower())

    def search_variables(self, query: str) -> list[ModelVar]:
        q = query.lower()
        hits = []
        for v in self.variables:
            hay = f"{v.name} {v.kvar} {v.standard_name} {v.long_name} {v.description} {v.units}".lower()
            if q in hay:
                score = (0 if q in v.name.lower() or q in v.kvar.lower() else 1, v.name)
                hits.append((score, v))
        hits.sort(key=lambda x: x[0])
        return [v for _, v in hits]

    # ---- docs ----
    def list_docs(self) -> list[DocPage]:
        return sorted(self.docs.values(), key=lambda d: (d.order, d.name))

    def get_doc(self, name: str) -> DocPage | None:
        name = name.lower()
        for k, v in self.docs.items():
            if k.lower() in (name, name + ".md") or v.title.lower() == name:
                return v
        return None

    def search_docs(self, query: str, max_results: int = 20) -> list[dict]:
        q = query.lower()
        results: list[dict] = []
        for page in self.list_docs():
            for i, line in enumerate(page.text.splitlines(), 1):
                if q in line.lower():
                    results.append({"doc": page.name, "line": i, "text": line.strip()})
                    if len(results) >= max_results:
                        return results
        return results

    # ---- examples ----
    def list_examples(self) -> list[str]:
        return sorted(self.examples)

    def get_example(self, name: str) -> str | None:
        if name in self.examples:
            return self.examples[name]
        for k, v in self.examples.items():
            if k.lower() == name.lower() or k.lower() == (name + ".nml").lower():
                return v
        return None

    def search_examples(self, query: str) -> list[dict]:
        q = query.lower()
        out = []
        for name, content in sorted(self.examples.items()):
            for i, line in enumerate(content.splitlines(), 1):
                if q in line.lower():
                    out.append({"example": name, "line": i, "text": line.strip()})
        return out


def slug_to_title(name: str) -> str:
    base = re.sub(r"\.md$", "", name)
    return base.replace("_", " ").title()
