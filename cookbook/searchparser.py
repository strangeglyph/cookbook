import abc
from typing import Optional, List, Callable

from cookbook.cookbook import Recipe


class Filter:
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def passes(self, recipe: Recipe) -> bool:
        ...


class TagFilter(Filter):
    def __init__(self, tag: str):
        self.tag = tag

    def passes(self, recipe: Recipe) -> bool:
        return recipe.has_tag(self.tag)

    def __repr__(self):
        return f"[Tag: {self.tag}]"


class IngrFilter(Filter):
    def __init__(self, ingr: str):
        self.ingr = ingr

    def passes(self, recipe: Recipe) -> bool:
        return recipe.has_ingredient(self.ingr)

    def __repr__(self):
        return f"[Ingredient: {self.ingr}]"


class GenericFilter(Filter):
    def __init__(self, term: str):
        self.term = term

    def passes(self, recipe: Recipe) -> bool:
        return recipe.has_tag(self.term) or recipe.has_ingredient(self.term) or recipe.has_word(self.term)

    def __repr__(self):
        return f"[Generic: {self.term}]"


class Query(Filter):
    def __init__(self):
        self.filters: List[Filter] = []

    def add_filter(self, filter: Filter):
        self.filters.append(filter)

    def passes(self, recipe: Recipe) -> bool:
        for filter in self.filters:
            if not filter.passes(recipe):
                return False
        return True

    def __repr__(self):
        return f"[Query: {' AND '.join(map(repr, self.filters))}]"


class Parser:
    def __init__(self, inpt: str):
        self.input = inpt
        self.pos = 0

    def parse(self) -> Query:
        result = Query()
        next = self.word()
        while next:
            print(f"scanned {next}, peek: {self.peek()}")
            if next.lower() == "tag" and self.peek() == ':':
                self.char()  # skip ':'
                search_term = self.word()
                if search_term:
                    result.add_filter(TagFilter(search_term))
            elif next.lower() == "ingr" and self.peek() == ':':
                self.char()  # skip ':'
                search_term = self.word()
                if search_term:
                    result.add_filter(IngrFilter(search_term))
            else:
                result.add_filter(GenericFilter(next))
            next = self.word()

        return result

    def word(self) -> Optional[str]:
        c = self.char()
        while c == ':' or c == ' ':
            c = self.char()

        if not c:
            return None
        if c == '"':
            result = self.scan_till(['"'])
            self.char()  # skip "
            return result
        elif c == "'":
            result = self.scan_till(["'"])
            self.char()  # skip '
            return result
        else:
            return c + self.scan_till(["'", '"', ' ', ':'])

    def scan_till(self, end: List[str]) -> Optional[str]:
        res = self.char()
        if not res:
            return None

        while True:
            c = self.peek()

            if not c: return res
            if c == '\\':
                self.skip(1)
                next = self.char()
                if not next: return res
                res += next
            elif c in end:
                return res
            else:
                res += self.char()

    def char(self) -> Optional[str]:
        if self.pos >= len(self.input):
            return None
        c = self.input[self.pos]
        self.pos += 1
        return c

    def peek(self) -> Optional[str]:
        if self.pos >= len(self.input):
            return None
        return self.input[self.pos]

    def skip(self, amnt: int):
        self.pos += amnt