import flask
from flask import Flask, request
import os

import searchparser
from cookbook import Cookbook

app = Flask(__name__)
app.config.from_json("config.json")

book = Cookbook()


def lang():
    if request and request.cookies and "lang" in request.cookies:
        if request.cookies["lang"] in book.by_language:
            return request.cookies.get("lang")

    return app.config["defaultlang"]


@app.route('/')
def index():
    if request.args.get("lang") in book.by_language:
        resp = flask.make_response(
            flask.render_template('index.jinja2', langs=book.by_language.keys(), active_lang=request.args.get("lang")))
    else:
        resp = flask.make_response(
            flask.render_template('index.jinja2', langs=book.by_language.keys(), active_lang=lang()))

    # Fix broken cookies
    if request.cookies.get("lang") not in book.by_language:
        resp.set_cookie("lang", app.config["defaultlang"])

    # If a new language got specified, update cookies
    if request.args.get("lang") in book.by_language:
        resp.set_cookie("lang", request.args.get("lang"))
    return resp


@app.route('/search')
def search():
    query_str = request.args["query"]
    if not query_str:
        return flask.redirect('/')

    query = searchparser.Parser(query_str).parse()
    print(query)

    results = set()
    for recipe in book.by_language[lang()]:
        if query.passes(recipe):
            results.add(recipe)

    results = sorted(results, key=lambda r: r.name)
    for recipe in results:
        print(f"{recipe.name} [{recipe.lang}]")

    resp = flask.make_response(flask.render_template('listing.jinja2', results=results, active_lang=lang(), query=query_str))
    return resp


@app.route("/all")
def all():
    results = sorted(book.by_language[lang()], key=lambda r: r.name)
    return flask.make_response(flask.render_template('listing.jinja2', results=results, active_lang=lang()))


if __name__ == "__main__":
    extra_dirs = ["templates", "static"]
    extra_files = extra_dirs[:]
    for extra_dir in extra_dirs:
        for dirname, dirs, files in os.walk(extra_dir):
            for filename in files:
                filename = os.path.join(dirname, filename)
                if os.path.isfile(filename):
                    extra_files.append(filename)

    book, errors = Cookbook.load_folder(app.config["COOKBOOK_LOCATION"])
    print(f"Cookbook: {len(book.by_id)} recipes loaded")
    for language, collection in book.by_language.items():
        print(f"- {language}: {len(collection)}")
    if errors:
        print("The following errors occured while trying to load recipes:")
        for error in errors:
            print(f"- {error.args[0]}")

    if "defaultlang" not in app.config:
        app.config["defaultlang"] = max(book.by_language.keys(), key=(lambda k: len(book.by_language[k])))

    app.run(extra_files=extra_files)
    app.run()
