from setuptools import setup, find_packages
from codecs import open
from os import path
import re

here = path.abspath(path.dirname(__file__))

version_match = re.search(
    r'^__version__\s*=\s*"(.*)"',
    open('job_assist_skill.scraper/__init__.py').read(),
    re.M
)
if version_match:
    version = version_match.group(1)
else:
    raise RuntimeError("Unable to find version string in job_assist_skill.scraper/__init__.py")

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# Basic dependencies only (no database/storage dependencies)
basic_requirements = [
    'playwright>=1.40.0',
    'requests>=2.31.0',
    'lxml>=5.0.0',
    'pydantic>=2.0.0',
    'python-dotenv>=1.0.0',
    'aiofiles>=23.0.0',
]

setup(
    name='job-assist-skill',
    packages=find_packages(),
    version=version,
    description='AI-powered Career Assistant for LinkedIn: Search, Tailor, Apply',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Abdullah Madoun',
    author_email='your.email@example.com',
    url='https://github.com/AbdullahMadoun/JobAssistSkill',
    download_url='https://github.com/AbdullahMadoun/JobAssistSkill/archive/refs/tags/' + version + '.tar.gz',
    keywords=['linkedin', 'career-assistant', 'job-search', 'cv-tailoring', 'ai-agent', 'vibecoding'],
    license='Apache 2.0',
    python_requires='>=3.8',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
    install_requires=basic_requirements,
    include_package_data=True,
    project_urls={
        'Source': 'https://github.com/AbdullahMadoun/JobAssistSkill',
        'Documentation': 'https://github.com/AbdullahMadoun/JobAssistSkill#readme',
    },
)
