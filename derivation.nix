{ lib, pkgs, ... }:

pkgs.python3Packages.buildPythonPackage rec {
    pname = "cookbook";
    version = "0.2.0";
    src = ./.;

    propagatedBuildInputs = with pkgs.python3Packages; [ flask ruamel-yaml ];
    nativeBuildInputs = with pkgs.python3Package; [ poetry-core ];

    pyproject = true;
    buildSystem = with pkgs.python3Packages; [ poetry-core ];

    pythonImportsCheck = [ "flask" "ruamel.yaml" ];
    doCheck = false;

    postInstall = ''
        cp -r cookbook/static $out/static
        echo "from cookbook import app" > $out/wsgi.py
    '';

    meta = with lib; {
        homepage = "https://github.com/strangeglyph/cookbook";
        description = "Flask application to serve recipes";
        license = licenses.mit;
    };
}
