from setuptools import setup, find_packages

setup(
    name='pyDPres',
    version='0.1',
    package_dir={'': 'src'},
    packages=find_packages("src"),
    install_requires=[
        'Click',
        'appdirs',
        'sqlalchemy',
    ],
    entry_points='''
        [console_scripts]
        pyDPres=pyDPres:cli
    ''',
)
