[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "her2dish-counter"
version = "0.1.0"
description = "Research-use HER2-DISH counting support desktop application"
readme = "README.md"
requires-python = ">=3.10"
authors = [{name = "HER2-DISH Counter Contributors"}]
license = {text = "Research use only - internal development"}
dependencies = [
    "PySide6>=6.6",
    "opencv-python>=4.8",
    "numpy>=1.24",
    "pandas>=2.0",
    "Pillow>=10.0",
]

[project.optional-dependencies]
dev = ["pytest>=7.4"]

[project.scripts]
her2dish-counter = "her2dish.main:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
