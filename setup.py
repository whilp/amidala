from setuptools import setup

meta = dict(
    name             = "amidala",
    version          = "0.0.1",
    packages         = ["amidala"],
    install_requires = [
        "boto",
        "docopt",
    ],
    scripts = [
        "scripts/amidala",
        "scripts/amichroot",
    ],
    )

setup(**meta)
