from pathlib import Path

from setuptools import find_packages, setup


def load_requirements():
    requirements_path = Path(__file__).with_name("requirements.txt")
    requirements = []
    for line in requirements_path.read_text(encoding="utf-8").splitlines():
        requirement = line.split("#", 1)[0].strip()
        if requirement:
            requirements.append(requirement)
    return requirements

setup(
    name="travel_agent",
    version="0.1.0",
    packages=find_packages(),
    install_requires=load_requirements(),
    python_requires=">=3.11",
)
