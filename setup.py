from setuptools import setup

setup(
    name="cookbook",
    version="0.1.0",
    description="Flask application to serve recipes",
    license="Apache 2.0",
    author="glyph",
    author_email="mail <at> strangegly <dot> ph",
    url="github.com/strangeglyph/cookbook",
    packages=["cookbook"],
    install_requires=["flask", "ruamel.yaml"]
)

