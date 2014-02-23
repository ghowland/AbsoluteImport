from setuptools import setup, find_packages
setup(
    name = "AbsoluteImport",
    version = "2013.02.12.0",
    packages = find_packages(),

    include_package_data = True,
    package_data = {
    },

    install_requires = [],

    author = "Geoff Howland",
    author_email = "geoff@gmail.com",
    description = "AbsoluteImport ensures module and package imports always work, from relative or absolute path.  Cyclical imports are fine.",
    license = "MIT",
    keywords = "import path relative absolute module package",
    url = "http://code.google.com/p/absoluteimport/",

    classifiers = [
        "Development Status :: 4 - Beta", 
        "Intended Audience :: Developers", 
        "License :: OSI Approved :: MIT License", 
        "Natural Language :: English", 
        "Operating System :: OS Independent", 
        "Programming Language :: Python :: 3", 
        "Topic :: Utilities", 
    ],
)

