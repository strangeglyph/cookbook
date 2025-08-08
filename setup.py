from setuptools import setup

setup(
    name="cookbook",
    version="0.2.0",
    description="Flask application to serve recipes",
    license="MIT",
    author="glyph",
    author_email="mail <at> strangegly <dot> ph",
    url="github.com/strangeglyph/cookbook",
    packages=["cookbook"],
    package_data={
      "cookbook": ['static/*', 'Templates/*', 'localization/*'],
    },
    install_requires=["flask", "ruamel.yaml"]
)

