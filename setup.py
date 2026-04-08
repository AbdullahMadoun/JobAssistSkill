from pathlib import Path

from setuptools import find_packages, setup


ROOT = Path(__file__).parent


setup(
    name="job-assist-skill",
    version="3.2.0",
    description="Agent-operated LinkedIn search skill with local prompt-driven CV tailoring",
    long_description=(ROOT / "README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    packages=find_packages(include=["job_assist_skill*"]),
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=[
        "aiofiles>=23.0.0",
        "flask>=3.0.0",
        "lxml>=5.0.0",
        "playwright>=1.40.0",
        "pydantic>=2.0.0",
        "PyPDF2>=3.0.0",
        "python-dotenv>=1.0.0",
        "PyYAML>=6.0",
        "requests>=2.31.0",
    ],
)
