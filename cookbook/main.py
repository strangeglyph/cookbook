import argparse

import flask
from flask import Flask, request, g
import os
import os.path
import sys
import json

from . import localization
from . import formatting
from . import searchparser
from .common import get_data_path
from .cookbook.cookbook import Cookbook
from .cookbook.errors import LoadException


app = Flask(__name__, template_folder=get_data_path("Templates"))
if os.getenv("COOKBOOK_CONFIG"):
    print(f"Loading config from {os.getenv('COOKBOOK_CONFIG')}")
    app.config.from_file(os.getenv("COOKBOOK_CONFIG"), load=json.load)
if os.getenv("EXTRA_COOKBOOK_CONFIG"): # for secrets
    print(f"Loading config from {os.getenv('EXTRA_COOKBOOK_CONFIG')}")
    app.config.from_file(os.getenv("EXTRA_COOKBOOK_CONFIG"), load=json.load)
app.config.from_prefixed_env()

def lang():
    if hasattr(g, "lang_code") and g.lang_code:
        return g.lang_code

    if 'lang' in request.cookies:
        return request.cookies.get('lang')

    return app.config["DEFAULT_LANG"]


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


@app.context_processor
def inject_site_info():
    root = app.config["APPLICATION_ROOT"]
    if root == "/":
        # Double slashes on the first segment of a domain-relative URL turns it into a protocol-relative URL
        # (i.e. the first segment is expected to be a domain name, not the first path segment),
        # so we turn the default application root of "/" into an empty string for our templates
        root = ""
    return dict(site_name=app.config["SITE_NAME"], base_url=app.config["BASE_URL"], root=root)

@app.context_processor
def inject_cookbook():
    return dict(book=book)


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

    results = sorted(results, key=lambda r: r.metadata.name)

    g.response.data = flask.render_template('listing.jinja2', results=results, query=query_str)
    return g.response


@app.route("/all")
@app.route("/<lang>/all")
def all():
    all_except_hidden = filter(lambda recipe: not recipe.metadata.hide_from_all, book.by_language[lang()])
    results = sorted(all_except_hidden, key=lambda r: r.metadata.name)
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
    elif app.config["DEFAULT_LANG"] in recipe_trans.translations:
        recipe = recipe_trans.translations[app.config["DEFAULT_LANG"]]
    else:
        recipe = list(recipe_trans.translations.values())[0]

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
def format_instr_part(value):
    return formatting.format_instr_part(value)

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
    if localization.is_localized(string, lang()):
        return localization.localize(string, lang())

    if localization.is_localized(string, app.config['DEFAULT_LANG']):
        return localization.localize(string, app.config['DEFAULT_LANG'])

    return localization.localize(string, 'en')


if "COOKBOOK_LOCATION" not in app.config:
    raise Exception("No COOKBOOK_LOCATION in config, was a config file provided? - Unable to continue.")

book, errors = Cookbook.load_folder(app.config["COOKBOOK_LOCATION"])
print(f"Cookbook: {len(book.by_id)} recipes loaded (path: {app.config['COOKBOOK_LOCATION']})")
for language, collection in book.by_language.items():
    print(f"- {language}: {len(collection)}")

if errors:
    print("The following errors occurred while trying to load recipes (These recipes may be ignored):\n")
    for error in errors:
        print(f"{error.args[0]}")
        if type(error) is LoadException:
            for note in error.context:
                print(f"  {note}")
            if error.cause:
                raise error.cause
        print()

if not book.by_id:
    print("I was unable to load any recipes whatsoever.")

if "DEFAULT_LANG" not in app.config:
    if not book.by_language:
        app.config["DEFAULT_LANG"] = "en"
    else:
        app.config["DEFAULT_LANG"] = max(book.by_language.keys(), key=(lambda k: len(book.by_language[k])))

if "SITE_NAME" not in app.config:
    app.config["SITE_NAME"] = "Cookbook"

if "BASE_URL" not in app.config:
    raise Exception("No BASE_URL in app config")

