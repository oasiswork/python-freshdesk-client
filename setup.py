#!/usr/bin/env python

from setuptools import setup, find_packages
import os

README = file(os.path.join(
    os.path.dirname(__file__),
    'README.md')).read()

setup(name='python-freshdesk-client',
      version='0.1',
      description='Wrapper arround freshdesk REST API',
      long_description=README,
      author='Jocelyn Delalande',
      author_email='jdelalande@oasiswork.fr',
      py_modules=['freshdesk_api'],
      install_requires=['requests'],

      classifiers=[
          'License :: OSI Approved :: MIT License',

          ]
      )
