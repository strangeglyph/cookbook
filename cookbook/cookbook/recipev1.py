import difflib
import os
from typing import List, Dict, Union, Optional, Set
from ruamel.yaml import YAML, yaml_object

from cookbook.localization import localize

from .errors import LoadException
from .recipev2 import RecipeV2, RecipeMeta, RecipeSection, RecipeStep as StepV2

yaml = YAML()
yaml.indent(mapping=2, sequence=4, offset=2)


class Ingredient:
    def __init__(self, serves: int, ingredient: str, amount: int = None, unit: str = None):
        self.ingredient: str = ingredient
        self.amount: Optional[int] = amount
        if self.amount:
            self.amount_per_serving = self.amount / serves
        else:
            self.amount_per_serving = None
        self.unit: Optional[str] = unit


class RecipeStep:
    def __init__(self, serves: int, instructions: str,
                 ingredients: List[Dict[str,str]] = None,
                 internal_ingredients: List[str] = None,
                 hidden_ingredients: List[str] = None,
                 yields: Union[str, List[str]] = None):
        self.instructions: str = instructions

        self.ingredients: List[Ingredient] = []
        if ingredients is not None:
            for i, ingredient in enumerate(ingredients):
                try:
                    self.ingredients.append(Ingredient(serves, **ingredient))
                except TypeError as e:
                    if "ingredient" in ingredient and type(ingredient) == map:
                        ing_id = f"{i + 1} ({ingredient['ingredient']})"
                    else:
                        ing_id = f"{i + 1}"
                    if e.args and 'required positional argument' in e.args[0]:
                        field = e.args[0].split('\'')[1]
                        raise LoadException(f"ingredient {ing_id} is missing a required field: '{field}'")
                    elif e.args and 'unexpected keyword argument' in e.args[0]:
                        field = e.args[0].split('\'')[1]
                        raise LoadException(f"ingredient {ing_id} contains an unknown key: '{field}'")
                    elif e.args and 'must be a mapping' in e.args[0]:
                        raise LoadException(f"ingredient {ing_id} should be an object, but was a {type(ingredient)} ('{ingredient}')")
                    else:
                        raise e

        self.internal_ingredients: List[str] = internal_ingredients if internal_ingredients else []

        self.hidden_ingredients: List[str] = hidden_ingredients if hidden_ingredients else []

        self.yields: List[str] = []
        if yields is not None:
            if type(yields) == list:
                self.yields = yields
            else:
                self.yields = [yields]

    def rows(self):
        return max(1, len(self.ingredients) + len(self.internal_ingredients))


class RecipeV1:
    def __init__(self, recipe_folder: str, id: str, lang: str, name: str, serves: int,
                 servings_unit: str = None,
                 servings_increment: Union[float, int] = 1,
                 descr: str = None,
                 note: str = None,
                 tags: Union[str, List[str]] = None,
                 hide_from_all: bool = False,
                 related: List[str] = None,
                 prep: List[Dict[str, str]] = None,
                 mis_en_place: List[Dict[str, str]] = None,
                 cooking: List[Dict[str, str]] = None,
                 passive_cooking: List[Dict[str, str]] = None,
                 cooking2: List[Dict[str, str]] = None,
                 passive_cooking2: List[Dict[str, str]] = None):
        self.id: str = self.normalize_id(id)
        self.unformatted_id: str = id
        self.lang: str = lang
        self.name: str = name
        self.serves: int = serves
        self.hide_from_all: bool = hide_from_all
        self.servings_unit: Optional[str] = servings_unit
        self.servings_increment: Union[float, int] = servings_increment
        self.descr: Optional[str] = descr
        self.note: Optional[str] = note
        self.recipe_folder: str = recipe_folder
        self.word_bag: Set[str] = set()

        for word in name.split():
            self.word_bag.add(word.lower())
        if descr:
            for word in descr.split():
                self.word_bag.add(word.lower())
        if note:
            for word in note.split():
                self.word_bag.add(word.lower())

        self.total_ingredients: List[Ingredient] = []
        self.ingr_bag: Set[str] = set()

        self.related_recipes: List[Union[str, RecipeV1]] = []
        for related in (related or []):
            self.related_recipes.append(self.normalize_id(related))

        self.tags: List[str] = []
        self.tags_bag: Set[str] = set()
        if tags is not None:
            if type(tags) == str:
                tags = tags.split(',')
            for tag in tags:
                norm_tag = tag.lower().strip().strip(',')
                self.tags.append(norm_tag)
                self.tags_bag.add(norm_tag)

        self.prep: List[RecipeStep] = []
        self.parse_section("Prep", prep, self.prep)

        self.mis_en_place: List[RecipeStep] = []
        self.parse_section("Mis-en-place", mis_en_place, self.mis_en_place)

        self.cooking: List[RecipeStep] = []
        self.parse_section("Cooking", cooking, self.cooking)

        self.passive_cooking: List[RecipeStep] = []
        self.parse_section("Passive cooking", passive_cooking, self.passive_cooking)

        self.cooking2: List[RecipeStep] = []
        self.parse_section("Cooking pt. 2", cooking2, self.cooking2)

        self.passive_cooking2: List[RecipeStep] = []
        self.parse_section("Passive cooking pt. 2", passive_cooking2, self.passive_cooking2)

    def to_v2(self) -> RecipeV2:
        metadata = RecipeMeta()
        metadata.id = self.id
        metadata.lang = self.lang
        metadata.name = self.name
        metadata.serves = self.serves
        metadata.servings_unit = self.servings_unit
        metadata.servings_increment = self.servings_increment
        metadata.desc = self.descr
        metadata.note = self.note
        metadata.tags = self.tags
        metadata.related = self.related_recipes
        metadata.hide_from_all = self.hide_from_all

        sections = []
        def transfer_section(name, steps):
            if steps:
                new_steps = []
                for step in steps:
                    new_step = StepV2(self.serves, [ step.instructions ], step.ingredients or [], step.internal_ingredients or [], step.hidden_ingredients or [], step.yields or [])
                    new_steps.append(new_step)

                sections.append(RecipeSection(new_steps, name))

        transfer_section(localize("recipe.section.prep.heading", self.lang), self.prep)
        transfer_section(localize("recipe.section.misenplace.heading", self.lang), self.mis_en_place)
        transfer_section(localize("recipe.section.cooking.heading", self.lang), self.cooking)
        transfer_section(localize("recipe.section.passivecooking.heading", self.lang), self.passive_cooking)
        transfer_section(localize("recipe.section.cooking2.heading", self.lang), self.cooking2)
        transfer_section(localize("recipe.section.passivecooking2.heading", self.lang), self.passive_cooking2)

        return RecipeV2(metadata, sections)

    def normalize_id(self, id):
        return id.lower().replace(' ', '-')

    def parse_section(self, sec_name: str, yaml_section: List[Dict[str, str]], list_section: List[RecipeStep]):
        if yaml_section is not None:
            for i, step in enumerate(yaml_section):
                try:
                    rstep = RecipeStep(self.serves, **step)
                    list_section.append(rstep)
                    for ingr in rstep.ingredients:
                        self.merge_ingredient(ingr)
                except TypeError as e:
                    if e.args and 'required positional argument' in e.args[0]:
                        field = e.args[0].split('\'')[1]
                        raise LoadException(
                            f"Recipe {self.id}.{self.lang}: {sec_name} step {i + 1} is missing a required field: '{field}'")
                    elif e.args and 'unexpected keyword argument' in e.args[0]:
                        field = e.args[0].split('\'')[1]
                        raise LoadException(
                            f"Recipe {self.id}.{self.lang}: {sec_name} step {i + 1} contains an unknown key: '{field}'")
                    else:
                        raise e
                except LoadException as e:
                    e.args = (f"Recipe {self.id}.{self.lang}: {sec_name} step {i + 1}: {e.args[0]}",)
                    raise e

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
                self.total_ingredients.append(Ingredient(self.serves, new_ingr.ingredient, new_ingr.amount, new_ingr.unit))
            else:  # ingredients with amounts go before ingredients without amounts
                i = 0
                while i < len(self.total_ingredients):
                    if not self.total_ingredients[i].amount:
                        break
                    i += 1
                self.total_ingredients.insert(i, Ingredient(self.serves, new_ingr.ingredient, new_ingr.amount, new_ingr.unit))

    def has_ingredient(self, wanted_ingr: str) -> bool:
        return wanted_ingr.lower() in self.ingr_bag

    def has_ingredient_approx(self, wanted_ingr: str) -> bool:
        return self.has_ingredient(wanted_ingr) or any(difflib.get_close_matches(wanted_ingr.lower(), self.ingr_bag, cutoff=0.8))

    def has_tag(self, wanted_tag: str) -> bool:
        return wanted_tag.lower() in self.tags_bag

    def has_tag_approx(self, wanted_tag: str) -> bool:
        return self.has_tag(wanted_tag) or any(difflib.get_close_matches(wanted_tag.lower(), self.tags_bag, cutoff=0.8))

    def has_word(self, wanted_word: str) -> bool:
        return wanted_word.lower() in self.word_bag

    def has_word_approx(self, wanted_word: str) -> bool:
        return self.has_word(wanted_word) or any(difflib.get_close_matches(wanted_word.lower(), self.word_bag, cutoff=0.8))

    def image_path(self) -> str:
        """
        Search for a matching image in the images/ subfolder of the recipe folder. Image name
        should be either the same as the recipe file name or in slug format (all lower case and spaces
        replaced with dashes)
        """
        if os.path.exists(os.path.join(self.recipe_folder, "images", f"{self.unformatted_id}.png")):
            return f"images/{self.unformatted_id}.png"
        elif os.path.exists(os.path.join(self.recipe_folder, "images", f"{self.unformatted_id}.jpg")):
            return f"images/{self.unformatted_id}.jpg"
        elif os.path.exists(os.path.join(self.recipe_folder, "images", f"{self.id}.png")):
            return f"images/{self.id}.png"
        elif os.path.exists(os.path.join(self.recipe_folder, "images", f"{self.id}.jpg")):
            return f"images/{self.id}.jpg"
        else:
            return "static/no-image.png"

    @staticmethod
    def split_path(path: str) -> (str, str):
        _, fname = os.path.split(path)
        root, ext = os.path.splitext(fname)
        if ext != ".yml" and ext != ".yaml":
            raise LoadException(f"{path}: Expect yaml file, got {ext}")

        recipe_id, lang = os.path.splitext(root)
        lang = lang[1:]
        return recipe_id, lang

    @staticmethod
    def load(path: str, id, lang, filename) -> "RecipeV1":

        recipe_folder, _ = os.path.split(path)
        try:
            with open(path, 'r', encoding="utf-8") as f:
                recipe = RecipeV1(recipe_folder, id, lang, **yaml.load(f))
                return recipe
        except TypeError as e:
            if e.args and 'required positional argument' in e.args[0]:
                field = e.args[0].split('\'')[1]
                raise LoadException(f"Recipe {recipe_id}.{lang} is missing a required field: '{field}'")
            elif e.args and 'unexpected keyword argument' in e.args[0]:
                field = e.args[0].split('\'')[1]
                raise LoadException(f"Recipe {recipe_id}.{lang} contains an unknown key: '{field}'")
            else:
                raise e