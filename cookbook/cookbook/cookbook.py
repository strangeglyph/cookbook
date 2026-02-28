import os
from typing import List, Dict, Set
import os.path as ospath
import difflib

from .errors import LoadException
from .recipev1 import RecipeV1
from .recipev2 import RecipeV2

Recipe = RecipeV2


def normalize_id(id: str):
    return id.lower().replace(' ', '-')


class RecipeTranslations:
    def __init__(self):
        self.translations: Dict[str, Recipe] = {}

    def get_name(self, lang):
        if lang in self.translations:
            return self.translations[lang].metadata.name
        if 'en' in self.translations:
            return self.translations['en'].metadata.name
        return self.translations.values().__iter__().__next__().metadata.name


class Cookbook:
    def __init__(self, folder):
        self.folder = folder
        self.by_id: Dict[str, RecipeTranslations] = {}
        self.by_language: Dict[str, List[Recipe]] = {}
        self.by_lang_and_tag: Dict[str, Dict[str, List[Recipe]]] = {}
        self.tagcount_by_language: Dict[str, Dict[str, int]] = {}

    def validate_tags(self) -> List[LoadException]:
        tag_set: Dict[str, Set[str]] = {}
        warnings = []

        for lang, recipes in self.by_language.items():
            tag_set[lang] = set()

            for recipe in recipes:
                for tag in recipe.metadata.tags:
                    tag_set[lang].add(tag)

            for tag in tag_set[lang]:
                similar = difflib.get_close_matches(tag, tag_set[lang], cutoff=0.8)
                similar.remove(tag)
                if similar:
                    def recipe_list(other_tag):
                        return ', '.join(map(lambda r: r.metadata.id, self.by_language[lang][other_tag]))
                    def other_tag_list(tags):
                        return "\n".join(map(lambda t: f'    - {t} in {recipe_list(t)}', tags))
                    warnings.append(f"Tag '{tag}' of language {lang} potentially misspelled.\n"
                                    f"  Tag present in files: {recipe_list(tag)}\n"
                                    f"  Candidate tags:\n"
                                    f"{other_tag_list(similar)}")

        return warnings

    def validate_related(self) -> List[LoadException]:
        warnings = []

        for lang, recipes in self.by_language.items():
            for recipe in recipes:
                for related in recipe.metadata.related:
                    if related not in self.by_id:
                        similar = difflib.get_close_matches(related, self.by_id.keys(), cutoff=0.8)
                        warning = f"Recipe {recipe.metadata.id} references unknown related recipe {related}."
                        if similar:
                            warning += "\n  Possibly misspelled, candidates: " + ', '.join(similar)
                        warnings.append(LoadException(warning))
                    elif lang not in self.by_id[related].translations:
                        warning = f"Recipe {recipe.metadata.id} references {related} but {related} is not translated to {lang}"
                        warnings.append(LoadException(warning))

        return warnings

    def image_path(self, recipe) -> str:
        """
        Search for a matching image in the images/ subfolder of the recipe folder. Image name
        should be either the same as the recipe file name or in slug format (all lower case and spaces
        replaced with dashes)
        """
        if os.path.exists(os.path.join(self.folder, "images", f"{recipe.metadata.filename}.png")):
            return f"images/{recipe.metadata.filename}.png"
        elif os.path.exists(os.path.join(self.folder, "images", f"{recipe.metadata.filename}.jpg")):
            return f"images/{recipe.metadata.filename}.jpg"
        elif os.path.exists(os.path.join(self.folder, "images", f"{recipe.metadata.id}.png")):
            return f"images/{recipe.metadata.id}.png"
        elif os.path.exists(os.path.join(self.folder, "images", f"{recipe.metadata.id}.jpg")):
            return f"images/{recipe.metadata.id}.jpg"
        else:
            return "static/no-image.png"

    @staticmethod
    def load_folder(path: str) -> ("Cookbook", List[LoadException]):
        extension_map = {
            '.yml': RecipeV1,
            '.yaml': RecipeV1,
            '.recipe': RecipeV2,
        }

        book = Cookbook(path)
        errors = []
        if not ospath.exists(path):
            raise LoadException(f"No cookbook location at {path}")
        for root, _, files in os.walk(path):
            for file in files:
                try:
                    _, fname = os.path.split(file)
                    stem, extension = os.path.splitext(fname)

                    if extension not in extension_map:
                        continue

                    raw_id, lang = os.path.splitext(stem)
                    id = normalize_id(raw_id)
                    lang = lang[1:]
                    fpath = ospath.join(root, file)

                    recipe = extension_map[extension].load(fpath, id, lang, fname)

                    if type(recipe) is RecipeV1:
                        recipe = recipe.to_v2()

                    if id not in book.by_id:
                        book.by_id[id] = RecipeTranslations()
                    book.by_id[id].translations[lang] = recipe

                    if lang not in book.by_language:
                        book.by_language[lang] = []
                        book.by_lang_and_tag[lang] = {}
                        book.tagcount_by_language[lang] = {}
                    book.by_language[lang].append(recipe)

                    for tag in recipe.metadata.tags:
                        if tag not in book.by_lang_and_tag[lang]:
                            book.by_lang_and_tag[lang][tag] = []
                        book.by_lang_and_tag[lang][tag].append(recipe)

                        if not tag in book.tagcount_by_language[lang]:
                            book.tagcount_by_language[lang][tag] = 0
                        book.tagcount_by_language[lang][tag] += 1

                except LoadException as e:
                    e.add_note(f"in recipe '{file}'")
                    errors.append(e)
                except Exception as e:
                    load_error = LoadException(e.args[0])
                    load_error.add_note(f"in recipe '{file}'")
                    errors.append(load_error)

        errors += book.validate_tags()
        errors += book.validate_related()

        return book, errors

    def most_common_tags(self, lang, threshold=4):
        if lang not in self.tagcount_by_language:
            return []

        tag_counts = self.tagcount_by_language[lang]
        sorted_tags = list(map(lambda x: x[0], sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)))
        return sorted_tags[:threshold]