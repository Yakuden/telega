from setuptools import setup, find_packages
from os import path
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='telegaden',
    version='0.0.3',
    packages=find_packages(),
    url='https://github.com/Yakuden/telega',
    license='MIT',
    author='Yakuden',
    author_email='yakudenn@gmail.com',
    keywords='telegram telega client tglib',
    description='Python Telegram TDLib sync client',
    package_data={
        'telega': ['td_lib/linux/libtdjson.so', 'td_lib/linux/libtdjson.so.1.4.0'],
    },
    python_requires=">=3.5",
    install_requires=[],
    long_description=long_description,
    long_description_content_type='text/markdown'
)
