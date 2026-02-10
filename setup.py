from setuptools import setup, find_packages

# Include root package explicitly
packages = find_packages()
if "geometric_complexity" not in packages:
    packages.insert(0, "geometric_complexity")

setup(
    name="geometric_complexity",
    version="0.1.0",
    packages=packages,
    package_dir={"geometric_complexity": "."},
    install_requires=[
        "pandas",
        "numpy",
        "requests",
        "shapely",
        "geopandas",
    ],
    python_requires=">=3.7",
)
