import os
from typing import List, Dict, Union, Optional, Set
import os.path as ospath
import difflib
from ruamel.yaml import YAML, yaml_object

yaml = YAML()
yaml.indent(mapping=2, sequence=4, offset=2)


TAG_SET: Dict[str, Set[str]] = {}


def update_tag_set(lang: str, tag: str):
    if lang in TAG_SET:
        TAG_SET[lang].add(tag)
    else:
        TAG_SET[lang] = {tag}


def find_conflicting_tags(lang: str, tag: str) -> List[str]:
    if lang not in TAG_SET:
        return []
    return difflib.get_close_matches(tag, TAG_SET[lang], cutoff=0.8)


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


class Recipe:
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

        self.related_recipes: List[Union[str, Recipe]] = []
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

                conflicts = find_conflicting_tags(lang, norm_tag)
                for conflict in conflicts:
                    if conflict == norm_tag:
                        continue
                    print(f"Potentially misspelled tag in {id}.{lang}: {norm_tag} / Already known: {conflict}")
                update_tag_set(lang, norm_tag)

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
            return f"/images/{self.unformatted_id}.png"
        elif os.path.exists(os.path.join(self.recipe_folder, "images", f"{self.unformatted_id}.jpg")):
            return f"/images/{self.unformatted_id}.jpg"
        elif os.path.exists(os.path.join(self.recipe_folder, "images", f"{self.id}.png")):
            return f"/images/{self.id}.png"
        elif os.path.exists(os.path.join(self.recipe_folder, "images", f"{self.id}.jpg")):
            return f"/images/{self.id}.jpg"
        else:
            return "/static/no-image.png"

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

        recipe_folder, _ = os.path.split(path)
        recipe_id, lang = Recipe.split_path(path)
        try:
            with open(path, 'r', encoding="utf-8") as f:
                recipe = Recipe(recipe_folder, recipe_id, lang, **yaml.load(f))
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


class RecipeTranslations:
    def __init__(self):
        self.translations: Dict[str, Recipe] = {}


class Cookbook:
    def __init__(self):
        self.by_id: Dict[str, RecipeTranslations] = {}
        self.by_language: Dict[str, List[Recipe]] = {}
        self.tagcount_by_language: Dict[str, Dict[str, int]] = {}

    @staticmethod
    def load_folder(path: str) -> ("Cookbook", List[LoadException]):
        book = Cookbook()
        errors = []
        if not ospath.exists(path):
            raise LoadException(f"No cookbook location at {path}")
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
                        book.tagcount_by_language[recipe.lang] = {}
                    book.by_language[recipe.lang].append(recipe)

                    for tag in recipe.tags_bag:
                        if tag not in book.tagcount_by_language[recipe.lang]:
                            book.tagcount_by_language[recipe.lang][tag] = 0
                        book.tagcount_by_language[recipe.lang][tag] += 1
                except LoadException as e:
                    errors.append(e)

        # Postprocess "related recipes"
        for language in book.by_language.keys():
            for recipe in book.by_language[language]:
                related: List[Recipe] = []
                for related_id in recipe.related_recipes:
                    if related_id not in book.by_id:
                        errors.append(LoadException(f"Recipe {recipe.id}.{language} references related recipe {related_id}, but it does not exist"))
                        continue
                    if language not in book.by_id[related_id].translations:
                        errors.append(LoadException(f"Recipe {recipe.id}.{language} references related recipe {related_id}, but it does not support the language {language}"))
                        continue
                    related.append(book.by_id[related_id].translations[language])

        return book, errors

    def most_common_tags(self, lang, threshold=4):
        tag_counts = self.tagcount_by_language[lang]
        sorted_tags = list(map(lambda x: x[0], sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)))
        return sorted_tags[:threshold]