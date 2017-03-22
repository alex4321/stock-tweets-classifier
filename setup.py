from setuptools import setup, find_packages


setup(
    name='twitter_classifier',
    version='0.1.4.5',
    description='Watson-based Twitter sentiment classifier "API"',
    author='Alexander Pozharskiy',
    author_email='gaussmake@gmail.com',
    classifiers=[
        'Programming Language :: Python :: 3.5',
    ],
    packages=['twitter_classifier'],
    install_requires=[
        'peony-twitter',
        'aiopg',
        'aiohttp',
        'tornado'
    ],
    package_data={
        'twitter_classifier': ['config.json']
    },
    entry_points={
        'console_scripts': 'twitter_classifier_server=twitter_classifier:server_main'
    }
)