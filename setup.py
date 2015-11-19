from setuptools import setup, find_packages

version = '0.1.17'

setup(
    name='tangentdeployer',
    package_dir={'': 'src'},
    packages=find_packages('src'),
    include_package_data=True,
    version=version,
    description='A Fabric deploy script for AWS based projects',
    author='Chris McKinnel',
    author_email='chris.mckinnel@tangentsnowball.com',
    url='https://github.com/tangentlabs/tangent-deployer',
    download_url='https://github.com/tangentlabs/tangent-deployer/tarball/%s' % version,
    keywords=['deployment', 'fabric', 'tangent'],
    classifiers=[],
    install_requires=['jinja2==2.7.3']
)
