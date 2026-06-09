#!/usr/bin/env python3
"""Setup for ProsodyPrompt."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="prosodyprompt",
    version="0.3.0",
    author="Lydia Krifka",
    author_email="lydiakrifka@gmail.com",
    description="Linguistic prosody annotation environment and field-research toolkit",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kdlydia/ProsodyPrompt",
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.11",
    install_requires=[
        "librosa>=0.10.0",
        "numpy>=1.21.0",
        "scipy>=1.7.0",
        "soundfile>=0.12.0",
        "sounddevice>=0.4.5",
        "torchaudio>=2.0.0",
        "torch>=2.0.0",
        "torchcrepe>=0.0.20",
        "parselmouth>=0.4.0",
        "textgrid>=1.5",
        "matplotlib>=3.5.0",
        "opencv-python>=4.6.0",
        "pythonosc>=1.1.1",
    ],
    extras_require={
        "speech_recognition": [
            "openai-whisper>=20231117",
            "whisperx>=3.1.0",
        ],
        "alignment": [
            "Montreal-Forced-Aligner>=3.0.0",
        ],
        "spatial": [
            "spaudiopy>=0.1.2",
        ],
    },
    entry_points={
        "console_scripts": [
            "prosodyprompt=linux.run:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Intended Audience :: Science/Research",
        "Topic :: Multimedia :: Sound/Audio :: Analysis",
    ],
)
