{ pkgs, lib, config, inputs, ... }:
let 
  cookbook = pkgs.callPackage ./derivation.nix {};
  cookbook-python = pkgs.python3.withPackages (_: [ cookbook ]);
  recipes = pkgs.fetchgit {
    url = "https://github.com/strangeglyph/cookbook-recipes";
    rev = "refs/heads/master";
    hash = "sha256-aq6etAI0BIWyxmQzK2Fha109XQIFP1WPw6uW2DUeX7g=";
  };
  json = pkgs.formats.json {};
  dev-config-file = json.generate "cookbook-dev-config.json" {
    DEBUG = true;
    COOKBOOK_LOCATION = "${recipes}";
    SECRET_KEY = "123";
    DEFAULT_LANG = "en";
    BASE_URL = "http://localhost";
    SITE_NAME = "Cookbook (Dev)";
  };
in 
{
  packages = [
    cookbook-python
    pkgs.python313Packages.flask
  ];

  env = {
    COOKBOOK_CONFIG = "${dev-config-file}";
  };

  languages = {
    python = {
      enable = true;
      lsp.enable = true;
      uv.enable = true;
    };
  };

  processes = {
    flask = {
      exec = "${lib.getExe cookbook-python} -m flask --app cookbook:app --debug run";
      ready = {
        http.get = {
          port = 5000;
          path = "/";
        };
        initial_delay = 1;
        period = 1;
      };
    };
  };
  # See full reference at https://devenv.sh/reference/options/
}
