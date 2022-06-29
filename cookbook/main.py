import flask
from flask import Flask, request, g
import os
import os.path
import sys
import json

from ruamel.yaml import YAML

from cookbook import formatting
from cookbook import searchparser
from cookbook.cookbook import Cookbook


def get_data_path(relpath: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relpath)


app = Flask(__name__, template_folder=get_data_path("Templates"))
if len(sys.argv) > 1:
    print(sys.argv)
    app.config.from_file(sys.argv[1], load=json.load)
else:
    app.config.from_file("../config.json", load=json.load)

book = Cookbook()
yaml = YAML()

LOC_FILES = {}
for file in os.listdir(get_data_path("localization")):
    if os.path.splitext(file)[1] == '.yml':
        lang = os.path.splitext(file)[0]
        print(f"Loading localization file for {lang}")
        loc_file_path = os.path.join(get_data_path("localization"), file)
        with open(loc_file_path) as loc_file:
            LOC_FILES[lang] = yaml.load(loc_file)


def lang():
    if hasattr(g, "lang_code") and g.lang_code:
        return g.lang_code

    if 'lang' in request.cookies:
        return request.cookies.get('lang')

    return app.config["defaultlang"]


@app.url_defaults
def add_lang_to_route(endpoint, values):
    if 'lang' in values:
        return
    print(f"Current language is {lang()}")
    if app.url_map.is_endpoint_expecting(endpoint, 'lang'):
        values['lang'] = lang()


@app.url_value_preprocessor
def pull_lang(endpoint, values):
    g.response = flask.make_response()
    if not values:
        return
    lang_code = values.pop('lang', None)
    if lang_code:
        g.lang_code = lang_code
        g.response.set_cookie('lang', lang_code)


@app.context_processor
def inject_language_stuff():
    return dict(active_lang=lang(), localize=localize)


@app.route('/')
@app.route('/<lang>/')
def index():
    g.response.data = flask.render_template('index.jinja2', langs=book.by_language.keys(), most_common_tags=book.most_common_tags(lang()))
    return g.response


@app.route('/search')
@app.route('/<lang>/search')
def search():
    query_str = request.args["query"]
    if not query_str:
        return flask.redirect('/all')

    query = searchparser.Parser(query_str).parse()

    results = set()
    for recipe in book.by_language[lang()]:
        if query.passes(recipe):
            results.add(recipe)

    results = sorted(results, key=lambda r: r.name)

    g.response.data = flask.render_template('listing.jinja2', results=results, query=query_str)
    return g.response


@app.route("/all")
@app.route("/<lang>/all")
def all():
    all_except_hidden = filter(lambda recipe: not recipe.hidden_from_all, book.by_language[lang()])
    results = sorted(all_except_hidden, key=lambda r: r.name)
    g.response.data = flask.render_template('listing.jinja2', results=results)
    return g.response


@app.route("/recipe/<recipe_id>")
@app.route("/<lang>/recipe/<recipe_id>")
def recipe(recipe_id: str):
    if recipe_id not in book.by_id:
        g.response.data = flask.render_template('listing.jinja2', results=[])
        return g.response

    recipe_trans = book.by_id[recipe_id]
    if lang() in recipe_trans.translations:
        recipe = recipe_trans.translations[lang()]
    elif app.config["defaultlang"] in recipe_trans.translations:
        recipe = recipe_trans.translations[app.config["defaultlang"]]
    else:
        recipe = next(recipe_trans.translations.values())

    g.response.data = flask.render_template('recipe.jinja2', recipe=recipe, recipe_trans=recipe_trans)
    return g.response


@app.route("/images/<path:path>")
def images(path):
    return flask.send_from_directory(os.path.join(app.config["COOKBOOK_LOCATION"], "images"), path)


@app.template_filter()
def format_num(value):
    if not value:
        return ""
    try:
        return formatting.format_num(float(value))
    except ValueError:
        return value


@app.template_filter()
def round_up(value):
    if not value:
        return ""
    try:
        return formatting.round_up(float(value))
    except ValueError:
        return value


@app.template_filter()
def flatmap(xs, attr):
    return [item for x in xs for item in getattr(x, attr)]


@app.template_filter()
def mapnone(xs, val):
    return [item if item else val for item in xs]


def localize(string):
    if lang() in LOC_FILES and string in LOC_FILES[lang()]:
        return LOC_FILES[lang()][string]
    elif app.config['defaultlang'] in LOC_FILES and string in LOC_FILES[app.config['defaultlang']]:
        return LOC_FILES[app.config['defaultlang']][string]
    elif string in LOC_FILES['en']:
        return LOC_FILES['en'][string]
    else:
        return string


book, errors = Cookbook.load_folder(app.config["COOKBOOK_LOCATION"])
print(f"Cookbook: {len(book.by_id)} recipes loaded (path: {app.config['COOKBOOK_LOCATION']})")
for language, collection in book.by_language.items():
    print(f"- {language}: {len(collection)}")
if errors:
    print("The following errors occurred while trying to load recipes:")
    for error in errors:
        print(f"- {error.args[0]}")

if "defaultlang" not in app.config:
    app.config["defaultlang"] = max(book.by_language.keys(), key=(lambda k: len(book.by_language[k])))

