import difflib
import itertools
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Union, Optional, Set, TextIO
import shlex

from .errors import LoadException


def normalize_id(id):
    return id.strip().lower().replace(' ', '-')

class RecipeMeta:
    def __init__(self):
        self.schema_version: int = 2
        self.id: str = None
        self.lang: str = None
        self.name: str = None
        self.raw_id: str = None
        self.serves: int = 1
        self.servings_unit: Optional[str] = None
        self.servings_increment: Union[float, int] = 1
        self.desc: Optional[str] = None
        self.note: Optional[str] = None
        self.tags: List[str] = []
        self.related: List[str] = []
        self.attribution: Optional[str] = None
        self.hide_from_all: bool = False

        self._set_attrs: set = set()


    def set_once(self, name, val):
        if not hasattr(self, name):
            raise LoadException(f'Invalid recipe meta attribute {name}')
        if name in self._set_attrs:
            raise LoadException(f'Recipe meta attribute {name} already set \n'
                                f'  old: {self.__getattribute__(name)}\n'
                                f'  new: {val}')
        self.__setattr__(name, val)
        self._set_attrs.add(name)

    def validate(self):
        if self.id is None:
            raise LoadException(f"Recipe {self.name}: id is required")
        if self.lang is None:
            raise LoadException(f"Recipe {self.id}: language is required")
        if self.raw_id is None:
            raise LoadException(f"Recipe {self.id}.{self.lang}: filename is required")
        if self.name is None:
            raise LoadException(f"Recipe {self.id}.{self.lang} name is required")
        if self.serves is None:
            raise LoadException(f"Recipe {self.id}.{self.lang} serving size (`serves`) is required")
        if self.schema_version != 2:
            raise LoadException(f"Recipe {self.id}.{self.lang}: schema version (`version`) expected to be 2, is {self.schema_version}")

    @staticmethod
    def read_multiline(file: TextIO) -> (str, str):
        acc = ""
        while True:
            line = file.readline()
            if line.startswith("  "):
                acc += line[1:] # keep one whitespace
            else:
                return acc, line

    @staticmethod
    def parse(file: TextIO, id, lang, raw_id) -> 'RecipeMeta':
        metadata = RecipeMeta()
        metadata.id = id
        metadata.lang = lang
        metadata.raw_id = raw_id

        line = file.readline()

        while line.strip() != "":
            if line.startswith("name "):
                metadata.set_once('name', line[5:].strip())
            elif line.startswith("serves "):
                parts = shlex.split(line)
                metadata.set_once('serves', int(parts[1]))
                if len(parts) > 2:
                    metadata.set_once('servings_unit', parts[2])
                if len(parts) > 3:
                    if "." in parts[3]:
                        metadata.set_once('servings_increment', float(parts[3]))
                    else:
                        metadata.set_once('servings_increment', int(parts[3]))
            elif line.startswith("desc "):
                beginning = line[5:].strip()
                acc, rem = RecipeMeta.read_multiline(file)
                line = rem
                metadata.set_once('desc', f'{beginning} {acc}')
                continue
            elif line.startswith("note "):
                beginning = line[5:].strip()
                acc, rem = RecipeMeta.read_multiline(file)
                line = rem
                metadata.set_once('note', f'{beginning} {acc}')
                continue
            elif line.startswith("tags "):
                tags = map(lambda tag: tag.strip().lower(), line[5:].split(","))
                metadata.tags.extend(tags)
            elif line.startswith("attrib "):
                metadata.set_once('attribution', line[6:].strip())
            elif line.startswith("related "):
                parts = map(lambda rel: normalize_id(rel), line[7:].split(","))
                metadata.related.extend(parts)
            elif line.startswith("hide"):
                metadata.set_once('hide_from_all', True)
            elif line.startswith("version "):
                metadata.set_once('schema_version', int(line[7:].strip()))

            line = file.readline()

        metadata.validate()
        return metadata

class Ingredient:
    def __init__(self, serves: float, ingredient: str, amount: float = None, unit: str = None):
        self.ingredient: str = ingredient
        self.amount: Optional[float] = amount
        if self.amount:
            self.amount_per_serving = self.amount / serves
        else:
            self.amount_per_serving = None
        self.unit: Optional[str] = unit

    @staticmethod
    def parse(line: str, serves: float) -> 'Ingredient':
        parts = shlex.split(line)
        if not parts:
            raise LoadException(f"Can't parse ingredient '{line}': missing information")

        try:
            if len(parts) == 1:
                return Ingredient(serves, parts[0])
            elif len(parts) == 2:
                return Ingredient(serves, parts[1], float(parts[0]))
            else:
                return Ingredient(serves, ' '.join(parts[2:]), float(parts[0]), parts[1])
        except ValueError:
            raise LoadException(f"Can't parse amount of ingredient '{line}' (lexed as {parts})")


@dataclass
class Scalar:
    amount: float
    amount_per_serving: float

InstrPart = Union[str, Scalar]

def split_instr(line: str, serves) -> List[InstrPart]:
    result = []
    parts = line.split()
    for part in parts:
        if part and part[0] == '{' and part[-1] == '}':
            amt = float(part[1:-1])
            result.append(Scalar(amt, amt / serves))
        else:
            result.append(part)

    return result

@dataclass
class RecipeStep:
    serves: float
    instructions: List[InstrPart]
    ingredients: List[Ingredient]
    internal_ingredients: List[str]
    hidden_ingredients: List[str]
    yields: List[str]
    no_dep: bool = False
    upstream: List["RecipeStep"] = field(default_factory=list)
    downstream: List["RecipeStep"] = field(default_factory=list)

    def rows(self):
        return max(1, len(self.ingredients) + len(self.internal_ingredients))

    @staticmethod
    def parse(file: TextIO, serves: float) -> 'RecipeStep':
        ingredients: List[Ingredient] = []
        internal_ingredients: List[str] = []
        hidden_ingredients: List[str] = []
        instructions: List[InstrPart] = []
        yields: List[str] = []
        no_dep = False

        line = file.readline()
        while line.strip() != "":
            if line.startswith("- "):
                ingredients.append(Ingredient.parse(line[2:], serves))
            elif line.startswith("= "):
                internal_ingredients.append(line[2:].strip())
            elif line.startswith("@nodep"):
                no_dep = True
            elif line.startswith("@ "):
                hidden_ingredients.append(line[2:].strip())
            elif line.startswith("-> "):
                yields.append(line[3:].lower().strip())
            else:
                instructions += split_instr(line.strip(), serves)
            line = file.readline()

        return RecipeStep(serves, instructions, ingredients, internal_ingredients, hidden_ingredients, yields, no_dep)

@dataclass
class RecipeSection:
    steps: List[RecipeStep]
    heading: Optional[str] = None


class RecipeV2:
    def __init__(self,
                 metadata: RecipeMeta,
                 sections: List[RecipeSection]):
        self.metadata = metadata
        self.sections = sections
        self.root_steps = []

        self.word_bag: Set[str] = set()

        for word in metadata.name.split():
            self.word_bag.add(word.lower())
        if metadata.desc:
            for word in metadata.desc.split():
                self.word_bag.add(word.lower())
        if metadata.note:
            for word in metadata.note.split():
                self.word_bag.add(word.lower())

        self.total_ingredients: List[Ingredient] = []
        self.ingr_bag: Set[str] = set()

        for section in sections:
            for step in section.steps:
                for ingredient in step.ingredients:
                    self.merge_ingredient(ingredient)

    def merge_ingredient(self, new_ingr: Ingredient):
        found = False
        for old_ingr in self.total_ingredients:
            if old_ingr.ingredient == new_ingr.ingredient:
                if old_ingr.unit == new_ingr.unit:
                    if new_ingr.amount and not old_ingr.amount:
                        old_ingr.amount = new_ingr.amount
                        old_ingr.amount_per_serving = new_ingr.amount_per_serving
                    elif new_ingr.amount and old_ingr.amount:
                        old_ingr.amount += new_ingr.amount
                        old_ingr.amount_per_serving += new_ingr.amount_per_serving
                    found = True
                # TODO unit conversion
        if not found:
            self.ingr_bag.add(new_ingr.ingredient.lower())
            if not new_ingr.amount:  # ingredients without amounts go to the end
                self.total_ingredients.append(Ingredient(self.metadata.serves, new_ingr.ingredient, new_ingr.amount, new_ingr.unit))
            else:  # ingredients with amounts go before ingredients without amounts
                i = 0
                while i < len(self.total_ingredients):
                    if not self.total_ingredients[i].amount:
                        break
                    i += 1
                self.total_ingredients.insert(i, Ingredient(self.metadata.serves, new_ingr.ingredient, new_ingr.amount, new_ingr.unit))

    def has_ingredient(self, wanted_ingr: str) -> bool:
        return wanted_ingr.lower() in self.ingr_bag

    def has_ingredient_approx(self, wanted_ingr: str) -> bool:
        return self.has_ingredient(wanted_ingr) or any(difflib.get_close_matches(wanted_ingr.lower(), self.ingr_bag, cutoff=0.8))

    def has_tag(self, wanted_tag: str) -> bool:
        return wanted_tag.lower() in self.metadata.tags

    def has_tag_approx(self, wanted_tag: str) -> bool:
        return self.has_tag(wanted_tag) or any(difflib.get_close_matches(wanted_tag.lower(), self.metadata.tags, cutoff=0.8))

    def has_word(self, wanted_word: str) -> bool:
        return wanted_word.lower() in self.word_bag

    def has_word_approx(self, wanted_word: str) -> bool:
        return self.has_word(wanted_word) or any(difflib.get_close_matches(wanted_word.lower(), self.word_bag, cutoff=0.8))

    def build_dep_graph(self):
        first = True
        prev_step: RecipeStep = None
        yields = dict()


        for i, section in enumerate(self.sections):
            for j, step in enumerate(section.steps):
                if first:
                    self.root_steps.append(step)
                    if step.internal_ingredients or step.hidden_ingredients:
                        raise LoadException(f"First step has internal dependencies ({step.internal_ingredients}, {step.hidden_ingredients}). Consider reordering the recipe.")
                    first = False
                elif step.no_dep:
                    self.root_steps.append(step)
                    if step.internal_ingredients or step.hidden_ingredients:
                        raise LoadException(f"Step #{j+1} in section #{i+1} is marked as nodep but has internal dependencies.")
                elif not (step.internal_ingredients or step.hidden_ingredients):
                    prev_step.downstream.append(step)
                    step.upstream.append(prev_step)
                else:
                    for dep_name in map(lambda s: s.lower(), itertools.chain(step.internal_ingredients, step.hidden_ingredients)):
                        if dep_name not in yields:
                            similar = difflib.get_close_matches(dep_name, yields.keys(), cutoff=0.8)
                            error_msg = f"Step #{j + 1} in section #{i + 1} has internal dependency '{dep_name}' but no such yield exists."
                            if similar:
                                error_msg += f"\n  Potential misspellings: {similar}"
                            raise LoadException(error_msg)
                        yields[dep_name].downstream.append(step)
                        step.upstream.append(yields[dep_name])
                for _yield in step.yields:
                    if _yield in yields:
                        raise LoadException(f"Step #{j+1} in section #{i+1} redefines yield '{_yield}'.")
                    yields[_yield] = step
                prev_step = step

        for (_yield, step) in yields.items():
            found = False
            for downstream in step.downstream:
                for downstream_dep in map(lambda s: s.lower(), itertools.chain(downstream.internal_ingredients, downstream.hidden_ingredients)):
                    if _yield == downstream_dep:
                        found = True
                        break
            if not found:
                raise LoadException(f"Yield {_yield} defined but never used")

    @staticmethod
    def load(path: Path, id, lang, raw_id) -> "RecipeV2":
        with open(path, encoding='utf-8') as file:
            return RecipeV2.parse(file, id, lang, raw_id)

    @staticmethod
    def parse(file: TextIO, id, lang, raw_id) -> 'RecipeV2':
        meta = RecipeMeta.parse(file, id, lang, raw_id)

        sections = []

        current_section_steps = []
        current_section_heading = None

        pos = file.tell()
        line = file.readline()
        while line:
            while line.strip() == "":
                pos = file.tell()
                line = file.readline()

            if line.startswith("# "):
                if current_section_heading:
                    sections.append(RecipeSection(current_section_steps, current_section_heading))

                current_section_heading = line[2:].strip()
                current_section_steps = []
            else:
                file.seek(pos)
                try:
                    current_section_steps.append(RecipeStep.parse(file, meta.serves))
                except LoadException as e:
                    e.add_note(f'In step #{len(current_section_steps) + 1} of section #{len(sections) + 1} ({current_section_heading if current_section_heading else "<untitled>"})')
                    raise e

            pos = file.tell()
            line = file.readline()

        if current_section_steps:
            sections.append(RecipeSection(current_section_steps, current_section_heading))

        recipe = RecipeV2(meta, sections)
        recipe.build_dep_graph()

        return recipe

