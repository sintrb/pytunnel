from setuptools import setup
import os, io
from pytunnel import __version__


here = os.path.abspath(os.path.dirname(__file__))
README = io.open(os.path.join(here, 'README.md'), encoding='UTF-8').read()
CHANGES = io.open(os.path.join(here, 'CHANGES.md'), encoding='UTF-8').read()
setup(name="pytunnel",
      version=__version__,
      keywords=('pytunnel', 'tunnel', 'proxy', 'socket'),
      description="A TCP tunnel server/client by Python.",
      long_description=README + '\n\n\n' + CHANGES,
      long_description_content_type="text/markdown",
      url='https://github.com/sintrb/pytunnel/',
      author="trb",
      author_email="sintrb@gmail.com",
      packages=['pytunnel'],
      install_requires=[],
      zip_safe=False
      )
