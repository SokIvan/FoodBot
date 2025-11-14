from setuptools import setup, find_packages

setup(
    name="food-bot",
    version="1.0.0",
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'food-bot=bot.__main__:main',
        ],
    },
)