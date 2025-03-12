from setuptools import setup, find_packages

setup(
    name="youtube_analysis",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "crewai>=0.28.0",
        "langchain>=0.0.335",
        "langchain-openai>=0.0.2",
        "youtube-transcript-api>=0.6.1",
        "python-decouple>=3.8",
        "crewai-tools>=0.1.6",
        "pyyaml>=6.0",
    ],
    python_requires=">=3.8",
    description="A CrewAI implementation for analyzing YouTube videos",
    author="Venkatesh Murugadas",
    url="https://github.com/VenkateshDas/youtube_analysis",
) 