# Table of Contents
* [About This Project](#about)
* [Deployment](#deployment)
  * [uWSGI and nginx](#deploy-uwsgi-nginx)
  * [Nix](#deploy-nix)
* [Writing Recipes](#writing-recipes)
  * [Images](#images)
  * [Recipe File Format](#ref-format)
    * [Top-Level Keys](#ref-toplevel)
    * [Recipe Steps](#ref-steps)
    * [Ingredients](#ref-ingredients)
* [Localization](#localization)

# <a name="about"></a> About this Project

Cookbook attempts to be a modern and simple website to display recipes. 
This means among other things:
* Lightweight websites with minimal javascript
* Necessary ingredients displayed next to each step
* Multi-language support

(TODO images)

# <a name="deployment"></a> Deployment
Cookbook is written as a WSGI service. It is recommend to run it via
[uWSGI](https://uwsgi-docs.readthedocs.io/en/latest/), though several other 
deployment options are available. Please see the 
[Flask deployment instructions](https://flask.palletsprojects.com/en/2.2.x/deploying/)
for in-depth information.

Please find example setup scenarios below:

## <a name="deploy-uwsgi-nginx"></a> uWSGI and nginx

### cookbook

Clone this repository to some location, e.g. `/usr/local/cookbook`. This means
you should find e.g. the following paths:

- `/usr/local/cookbook/README.md`
- `/usr/local/cookbook/cookbook/main.py`
- `/usr/local/cookbook/cookbook/static/`

Create a virtual env in `/usr/local/cookbook`, i.e. 

```shell
python3 -m venv /usr/local/cookbook/env
```

Activate the virtual env and install cookbook into it:

```shell
source /usr/local/cookbook/env/bin/activate
python3 -m pip install .
```

Create `/var/cookbook/`. In `/var/cookbook/recipes/`, put your recipes; in 
`/var/cookbook/recipes/images/`, put your images.

In `/var/cookbook/config.json`, put:

```json
{
  "COOKBOOK_LOCATION": "/var/cookbook/recipes",
  "SECRET_KEY": "YOUR-SECRET-KEY",
  "defaultlang": "en"
}
```

Replace all of these keys as necessary. `SECRET_KEY` should be any randomly
generated string, see the Flask config for more details. 


### uWSGI

Install [uWSGI](https://uwsgi-docs.readthedocs.io/en/latest/). Find (or create)
the configuration directory for uwsgi. We will assume `/var/uwsgi` for this
tutorial.

In `/var/uwsgi/server.json`, put
```json
{
  "uwsgi": {
    "emperor": "/var/uwsgi/vassals"
  }
}
```

In `/var/uwsgi/vassals/cookbook.json`, put
```json
{
  "uwsgi": {
    "chmod-socket": "664",
    "chown-socket": "uwsgi:www-data",
    "env": [
      "PATH=/usr/local/cookbook/env/bin"
    ],
    "master": true,
    "module": "cookbook:app",
    "plugin": "python3",
    "plugins": ["python3"],
    "pyargv": "/var/cookbook/config.json",
    "pyhome": "/usr/local/cookbook/env",
    "socket": "/run/uwsgi/cookbook.sock",
    "workers": 5
  }
}
```

Change the value of `chown-socket` to the user that runs -- or will run -- the 
uWSGI service and the group that runs -- or will run -- nginx service.

Set up a systemd service (if none comes with your distro) to start uwsgi. This
service should run as the user set in `chown-socket`. Start uwsgi with the option
`--json /var/uwsgi/server.json`, for example: 

```systemd
[Service]
User=uwsgi
Group=uwsgi
ExecStart=uwsgi --json /var/uwsgi/server.json
# More options here
```

Enable and start the uwsgi service:

```shell
systemctl enable uwsgi
systemctl start uwsgi
```

### nginx

Set up [nginx](https://www.nginx.com/). Amend the configuration for the 
server section where you intend to host the server as follows:

```nginx
http {
  include uwsgi_params;
  
  server {
    # other server config goes here...
    server_name your.cookbook.url;
    
    location / {
      uwsgi_pass unix:/run/uwsgi/cookbook.sock;
    }
    location /images/ {
      alias /var/cookbook/recipes/images/;
      expires 7d;
      add_header Cache-Control "public";
    }
    location /static/ {
      alias /usr/local/cookbook/cookbook/static/;
    }
  }
}
```

Enable and start nginx:

```shell
systemctl enable nginx
systemctl start nginx
```

Navigate to the URL set in `server_name` to verify that cookbook is deployed and
running.

## <a name="deploy-nix"></a> Nix

A nix module is being written. In the meantime, if you would like guidance on how
to set up cookbook via nix, please see [here](https://github.com/strangeglyph/nix-home/blob/master/config/services/cookbook.nix)
for some hints.

# <a name="writing-recipes"></a> Writing Recipes
Recipes are stored in yaml files. These files should all be stored in one folder, 
which should be provided to the cookbook service in the config file (`COOKBOOK_LOCATION`).

The file names should follow the following format: `<id>.<language>.yml` or 
`<id>.<language>.yaml`. The cookbook service will automatically aggregate recipes
with the same id but different language codes, see 'Localization' for more 
information.

#### A Note on Recipe Ids
Recipe ids exist in two variants: Unnormalized, as found in the file name, and
normalized, for internal handling (e.g. the recipe in `Chocolate Cake.en.yml`
would have an unnormalized id of `Chocolate Cake` and a normalized id 
of `chocolate-cake`). 

Whenever you as the user need to specify ids (e.g. for translations or for
linking related recipes), it is recommended you use unnormalized ids. This makes
recipes more readable for you, and allows the normalized format to change
without breaking your recipes.

## <a name="images"></a> Images
Recipes can have linked images. For now these are only displayed in the search
results. Images are loaded from a subfolder of the recipe folder. Specifically,
the image is looked up in the following order:

1. `<recipe-folder>/images/<unnormalized id>.png`
2. `<recipe-folder>/images/<unnormalized id>.jpg`
3. `<recipe-folder>/images/<normalized id>.png`
4. `<recipe-folder>/images/<normalized id>.jpg`

Note that the service performs no further processing of the image files, instead
serving the files directly (in fact, it is recommended to configure your webserver
such that the image folder is served without dispatching to the service). 
Therefore, images should be cropped to a 16:9 aspect ratio (the search listing 
scales the images to 250 x 141px) [n.b. subject to change].


## <a name="ref-format"></a> Recipe File Format
### <a name="ref-toplevel"></a> Top-Level Keys

| Key                  | Description                                                                                                                                                                                                                                                       | Default | Mandatory? |
|----------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------|------------|
| `name`               | Name of the recipe, as displayed in the search results and on the recipe.                                                                                                                                                                                         |         | **Yes**    |
| `serves`             | Number of servings in this recipe.                                                                                                                                                                                                                                |         | **Yes**    |
| `servings_unit`      | The "kind" of servings this recipe produces. Usually readers assume that servings refers to the number of people that you can feed with the given amounts. Override this here if it does not apply, (e.g. servings is the number of muffins this recipe produces) | n/a     |            |
| `servings_increment` | The change in servings when readers press the + or - buttons next to the servings.                                                                                                                                                                                | 1       |            |
| `descr`              | A brief (one to two sentence) description of the recipe, displayed in the search results.                                                                                                                                                                         | n/a     |            |
| `note`               | Additional information about the recipe, displayed on the recipe page (e.g. suitable side dishes, possible variations).                                                                                                                                           |         |            |
| `hide_from_all`      | Hide the recipe from the 'all recipes' overview page. The recipe will still appear in more specific searches.                                                                                                                                                     |         |            |
| `related`            | List of (normalized or unnormalized, see 'Recipe Ids') ids of related recipes.                                                                                                                                                                                    | []      |            |
| `tags`               | List or comma separated string of tags                                                                                                                                                                                                                            | []      |            |
| `prep`               | List of recipe steps (see 'Recipe Steps') for the prep stage: Things that can or should be prepared in advance.                                                                                                                                                   | []      |            |
| `mis_en_place`       | List of recipe steps for the mis-en-place phase: Preparing ingredients for assembly                                                                                                                                                                               | []      |            |
| `cooking`            | List of recipe steps for the cooking phase: Active or semi-active assembly                                                                                                                                                                                        | []      |            |
| `passive_cooking`    | List of recipe steps for the passive cooking phase: Extended hands-off cooking times                                                                                                                                                                              | []      |            |
| `cooking2`           | List of recipe steps for the second cooking phase: Active or semi-active steps following a passive cooking phase                                                                                                                                                  | []      |            |
| `passive_cooking2`   | List of recipe steps for the second passive cooking: Extended hands-off cooking times following a previous passive cooking phase                                                                                                                                  | []      |            |
 
### <a name="ref-steps"></a> Recipe Steps
| Key                    | Description                                                                                                                                        | Default | Mandatory? |
|------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------|---------|------------|
| `ingredients`          | List of ingredients (see 'Ingredients') for this step                                                                                              | []      |            |
| `internal_ingredients` | List of strings: Intermediate results (see `yields` field here) from previous steps, for semantic linking of steps. Displayed in the instructions. | []      |            |
| `hidden_ingredients`   | List of strings: As `internal_ingredients` but only for semantic linking of steps, *not* displayed in the instructions.                            | []      |            |
| `yields`               | String or list of strings: Intermediate result(s) produced by this step. Not mandatory, but recommend for all but the final step.                  | n/a     |            |
| `instructions`         | Preparatory instructions for this step (we recommend yaml multiline strings, see examples for more information).                                   |         | **Yes**    |

### <a name="ref-ingredients"></a> Ingredients
| Key          | Description                                                                              | Default | Mandatory? |
|--------------|------------------------------------------------------------------------------------------|---------|------------|
| `ingredient` | Name of the ingredient                                                                   |         | **Yes**    |
| `amount`     | Amount of the ingredient to use (just the number, see `unit` field for unit information) | n/a     |            |
| `unit`       | Unit that the amount is given in                                                         |         |            |

# <a name="localization"></a> Localization
The service attempts to serve one localized version of the website for each
language for which a recipe has been found. The recipe localization itself is
left up to the user. The website UI is localized with strings taken from 
`localization/<lang>.yml`. If the language has no localization file, or a 
localization key is not defined, the service first falls back on the `defaultlang` 
language (definable in the config, if undefined defaults to the language
with the most recipes), and barring that, English.

The default language of the website is `defaultlang`. Specific languages can be
requested by prefixing all paths on the website by the desired language code.
Additionally, all recipes will link to versions of the same recipe in different
languages.

The service attempts to remember the preferred (i.e. last-used) language
and serve that as a default in the future (needs work, might get removed in favor
of explicit language paths everywhere except the default landing page)