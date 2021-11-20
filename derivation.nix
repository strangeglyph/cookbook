{ lib, python3Packages }:

python3Packages.buildPythonApplication rec {
    pname = "cookbook";
    version = "0.1.0";
    src = ./.;

    propagatedBuildInputs = with python3Packages; [ flask ruamel-yaml ];

    pythonImportsCheck = [ "flask" "ruamel.yaml" ];
    doCheck = false;

    postInstall = "cp -r cookbook/static $out/static";

    meta = with lib; {
        homepage = "https://github.com/strangeglyph/cookbook";
        description = "Flask application to serve recipes";
        license = licenses.asl20;
    };
}
