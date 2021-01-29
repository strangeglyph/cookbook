import os
from typing import List, Dict, Union, Optional, Set
import os.path as ospath
from ruamel.yaml import YAML, yaml_object

yaml = YAML()
yaml.indent(mapping=2, sequence=4, offset=2)


class LoadException(Exception):
    def __init__(self, msg: str):
        super(LoadException, self).__init__(msg)


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
                 yields: Union[str, List[str]] = None):
        self.instructions: str = instructions

        self.ingredients: List[Ingredient] = []
        if ingredients is not None:
            for i, ingredient in enumerate(ingredients):
                try:
                    self.ingredients.append(Ingredient(serves, **ingredient))
                except TypeError as e:
                    if "ingredient" in ingredient and type(ingredient) == map:
                        ing_id = f"{i} ({ingredient['ingredient']})"
                    else:
                        ing_id = f"{i}"
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

        self.internal_ingredients: List[str] = []
        if internal_ingredients is not None:
            self.internal_ingredients = internal_ingredients

        self.yields: List[str] = []
        if yields is not None:
            if type(yields) == list:
                self.yields = yields
            else:
                self.yields = [yields]

    def rows(self):
        return max(1, len(self.ingredients) + len(self.internal_ingredients))


class Recipe:
    def __init__(self, id: str, lang: str, name: str, serves: int,
                 servings_unit: str = "",
                 servings_increment: Union[float, int] = 1,
                 note: str = None,
                 tags: Union[str, List[str]] = None,
                 prep: List[Dict[str, str]] = None,
                 mis_en_place: List[Dict[str, str]] = None,
                 cooking: List[Dict[str, str]] = None,
                 passive_cooking: List[Dict[str, str]] = None):
        self.id: str = id.lower().replace(' ', '-')
        self.lang: str = lang
        self.name: str = name
        self.serves: int = serves
        self.servings_unit: str = servings_unit
        self.servings_increment: Union[float, int] = servings_increment
        self.note: Optional[str] = note
        self.word_bag: Set[str] = set()

        for word in name.split():
            self.word_bag.add(word.lower())
        if note:
            for word in note.split():
                self.word_bag.add(word.lower())

        self.total_ingredients: List[Ingredient] = []
        self.ingr_bag: Set[str] = set()

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
        if prep is not None:
            for i, step in enumerate(prep):
                try:
                    rstep = RecipeStep(self.serves, **step)
                    self.prep.append(rstep)
                    for ingr in rstep.ingredients:
                        self.merge_ingredient(ingr)
                except TypeError as e:
                    if e.args and 'required positional argument' in e.args[0]:
                        field = e.args[0].split('\'')[1]
                        raise LoadException(f"Recipe {id}.{lang}: prep step {i} is missing a required field: '{field}'")
                    elif e.args and 'unexpected keyword argument' in e.args[0]:
                        field = e.args[0].split('\'')[1]
                        raise LoadException(f"Recipe {id}.{lang}: prep step {i} contains an unknown key: '{field}'")
                    else:
                        raise e
                except LoadException as e:
                    e.args = (f"Recipe {id}.{lang}: prep step {i}: {e.args[0]}",)
                    raise e

        self.mis_en_place: List[RecipeStep] = []
        if mis_en_place is not None:
            for i, step in enumerate(mis_en_place):
                try:
                    rstep = RecipeStep(self.serves, **step)
                    self.mis_en_place.append(rstep)
                    for ingr in rstep.ingredients:
                        self.merge_ingredient(ingr)
                except TypeError as e:
                    if e.args and 'required positional argument' in e.args[0]:
                        field = e.args[0].split('\'')[1]
                        raise LoadException(f"Recipe {id}.{lang}: mis-en-place step {i} is missing a required field: '{field}'")
                    elif e.args and 'unexpected keyword argument' in e.args[0]:
                        field = e.args[0].split('\'')[1]
                        raise LoadException(f"Recipe {id}.{lang}: mis-en-place step {i} contains an unknown key: '{field}'")
                    else:
                        raise e
                except LoadException as e:
                    e.args = (f"Recipe {id}.{lang}: mis-en-place step {i}: {e.args[0]}",)
                    raise e

        self.cooking: List[RecipeStep] = []
        if cooking is not None:
            for i, step in enumerate(cooking):
                try:
                    rstep = RecipeStep(self.serves, **step)
                    self.cooking.append(rstep)
                    for ingr in rstep.ingredients:
                        self.merge_ingredient(ingr)
                except TypeError as e:
                    if e.args and 'required positional argument' in e.args[0]:
                        field = e.args[0].split('\'')[1]
                        raise LoadException(f"Recipe {id}.{lang}: cooking step {i} is missing a required field: '{field}'")
                    elif e.args and 'unexpected keyword argument' in e.args[0]:
                        field = e.args[0].split('\'')[1]
                        raise LoadException(f"Recipe {id}.{lang}: cooking step {i} contains an unknown key: '{field}'")
                    else:
                        raise e
                except LoadException as e:
                    e.args = (f"Recipe {id}.{lang}: cooking step {i}: {e.args[0]}",)
                    raise e

        self.passive_cooking: List[RecipeStep] = []
        if passive_cooking is not None:
            for i, step in enumerate(passive_cooking):
                try:
                    rstep = RecipeStep(self.serves, **step)
                    self.passive_cooking.append(rstep)
                    for ingr in rstep.ingredients:
                        self.merge_ingredient(ingr)
                except TypeError as e:
                    if e.args and 'required positional argument' in e.args[0]:
                        field = e.args[0].split('\'')[1]
                        raise LoadException(f"Recipe {id}.{lang}: passive step {i} is missing a required field: '{field}'")
                    elif e.args and 'unexpected keyword argument' in e.args[0]:
                        field = e.args[0].split('\'')[1]
                        raise LoadException(f"Recipe {id}.{lang}: passive step {i} contains an unknown key: '{field}'")
                    else:
                        raise e
                except LoadException as e:
                    e.args = (f"Recipe {id}.{lang}: passive step {i}: {e.args[0]}",)
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

    def has_tag(self, wanted_tag: str) -> bool:
        return wanted_tag.lower() in self.tags_bag

    def has_word(self, wanted_word: str) -> bool:
        return wanted_word.lower() in self.word_bag

    @staticmethod
    def split_path(path: str) -> (str, str):
        _, fname = ospath.split(path)
        root, ext = ospath.splitext(fname)
        if ext != ".yml" and ext != ".yaml":
            raise LoadException(f"{path}: Expect yaml file, got {ext}")

        recipe_id, lang = ospath.splitext(root)
        lang = lang[1:]
        return recipe_id, lang

    @staticmethod
    def load(path: str) -> "Recipe":

        recipe_id, lang = Recipe.split_path(path)
        try:
            with open(path, 'r', encoding="utf-8") as f:
                recipe = Recipe(recipe_id, lang, **yaml.load(f))
                return recipe
        except TypeError as e:
            if e.args and 'required positional argument' in e.args[0]:
                field = e.args[0].split('\'')[1]
                raise LoadException(f"Recipe {recipe_id}.{lang} is missing a required field: '{field}'")
            else:
                raise e


class RecipeTranslations:
    def __init__(self):
        self.translations: Dict[str, Recipe] = {}


class Cookbook:
    def __init__(self):
        self.by_id: Dict[str, RecipeTranslations] = {}
        self.by_language: Dict[str, List[Recipe]] = {}

    @staticmethod
    def load_folder(path: str) -> ("Cookbook", List[LoadException]):
        book = Cookbook()
        errors = []
        for root, _, files in os.walk(path):
            for file in files:
                try:
                    if ospath.splitext(file)[1] != ".yml" and ospath.splitext(file)[1] != ".yaml":
                        continue

                    fpath = ospath.join(root, file)
                    recipe = Recipe.load(fpath)

                    if recipe.id not in book.by_id:
                        book.by_id[recipe.id] = RecipeTranslations()
                    book.by_id[recipe.id].translations[recipe.lang] = recipe

                    if recipe.lang not in book.by_language:
                        book.by_language[recipe.lang] = []
                    book.by_language[recipe.lang].append(recipe)
                except LoadException as e:
                    errors.append(e)

        return book, errors
