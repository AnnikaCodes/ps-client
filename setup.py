"""setup.py
    sets up the module
    by Annika, template from https://packaging.python.org/tutorials/packaging-projects/"""

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="ps-client",
    version="0.0.4",
    author="Annika",
    author_email="annika0uwu@gmail.com",
    description="A package for interactions with the Pokémon Showdown simulator.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/AnnikaCodes/ps-client",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        "pytz",
        "requests",
        "websocket_client"
    ],
    python_requires='>=3.6',
)
