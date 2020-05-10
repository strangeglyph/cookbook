from typing import Optional, List, Callable

from cookbook import Recipe


class Parser:
    def __init__(self, inpt: str):
        self.input = inpt
        self.pos = 0

    def parse(self) -> List[Callable[[Recipe], bool]]:
        result = []
        next = self.word()
        while next:
            if next == "tag" and self.peek() == ':':
                self.char()  # skip ':'
                search_term = self.word()
                if search_term:
                    result.append(lambda recipe: recipe.has_tag(search_term))
            elif next == "ingr" and self.peek() == ':':
                self.char()  # skip ':'
                search_term = self.word()
                if search_term:
                    result.append(lambda recipe: recipe.has_ingredient(search_term))
            else:
                result.append(lambda recipe: recipe.has_ingredient(next) or recipe.has_tag(next) or recipe.has_word(next))
            next = self.word()

        return result

    def word(self) -> Optional[str]:
        c = self.char()
        if not c:
            return None
        if c == '"':
            result = self.scan_till(['"'])
            self.char() # skip "
            return result
        elif c == "'":
            result = self.scan_till(["'"])
            self.char() # skip '
            return result
        else:
            return self.scan_till(["'", '"', ' ', ':'])

    def scan_till(self, end: List[str]) -> Optional[str]:
        res = self.char()
        if not res: return None

        while True:
            c = self.char()
            if not c: return res
            if c == '\\':
                next = self.char()
                if not next: return res
                res += next
            elif c in end:
                return res
            else:
                res += c

    def char(self) -> Optional[str]:
        if self.pos == len(self.input):
            return None
        c = self.input[self.pos]
        self.pos += 1
        return c

    def peek(self) -> Optional[str]:
        if self.pos == len(self.input):
            return None
        return self.input[self.pos]