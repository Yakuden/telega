from setuptools import setup, find_packages


setup(
    name='telegaden',
    version='1.1.8',
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
    install_requires=[]
)
