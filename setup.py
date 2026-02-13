"""
PyGAMIT-Bridge: GAMIT/GLOBK 现代数据格式桥接工具包
"""
from setuptools import setup, find_packages

setup(
    name='pygamit-bridge',
    version='0.1.0',
    description='A Python toolkit for automated GAMIT/GLOBK processing '
                'with modern RINEX and IGS product formats',
    author='Jinzhen Han',
    author_email='geumjin99@gmail.com',
    url='https://github.com/geumjin99/pygamit-bridge',
    packages=find_packages(),
    python_requires='>=3.7',
    install_requires=[],  # 仅使用标准库
    entry_points={
        'console_scripts': [
            'pygamit-bridge=pygamit_bridge.cli:main',
        ],
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
    ],
    keywords='GNSS GAMIT RINEX troposphere ZTD geodesy',
)
