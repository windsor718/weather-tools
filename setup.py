from setuptools import find_packages, setup

weather_dl_requirements = [
    "cdsapi",
    "ecmwf-api-client",
    "apache-beam[gcp]",
    "numpy>=1.19.1",
    "pandas",
    "xarray",
    "requests>=2.24.0",
    "firebase-admin>=5.0.0",
    "google-cloud-datastore>=1.15.0,<2",  # For compatability with apache-beam[gcp]
    "google-cloud-firestore",
    "urllib3==1.25.11",
    "pyparsing==2.4.2",  # Fix http2lib auth breakage

]

weather_mv_requirements = [
    "apache-beam[gcp]",
    "numpy",
    "pandas",
    "xarray",
    "google-cloud-bigquery",
    "pyparsing==2.4.2",  # Fix http2lib auth breakage
]

weather_sp_requirements = [
    "apache-beam[gcp]",
    "numpy>=1.20.3",
    "pygrib",
    "netcdf4",
]

test_requirements = [
    "pytype",
    "flake8",
    "pytest",
    "netcdf4",
    "numpy",
    "xarray",
]

setup(
    name='weather-tools',
    packages=find_packages(),
    author='Anthromets',
    author_email='anthromets-ecmwf@google.com',
    description='Apache Beam pipelines to make weather data accessible and useful.',
    long_description=open('README.md', 'r').read(),
    long_description_content_type='text/markdown',
    platforms=['darwin', 'linux'],
    python_requires='>=3.7, <4',
    install_requires=['apache-beam[gcp]'],
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
    scripts=['weather_dl/weather-dl', 'weather_dl/download-status',
             'weather_mv/weather-mv', 'weather_sp/weather-sp'],
    tests_require=test_requirements,
    extras_require={
        'dev': ['tox', 'sphinx', 'recommonmark'],
        'test': weather_dl_requirements + weather_mv_requirements + weather_sp_requirements + test_requirements,
    },
    project_urls={
        'Issue Tracking': 'https://github.com/googlestaging/weather-tools/issues',
    },
)
