# Copyright (c) 2019, IRIS-HEP
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
import io

from setuptools import find_packages, setup

with io.open('README.rst', 'rt', encoding='utf8') as f:
    readme = f.read()

setup(
    name='servicex',
    version='1.0.0',
    url='https://iris-hep.org',
    license='BSD',
    maintainer='ServiceX Team',
    maintainer_email='bengal1@illinois.edu',
    description='REST Frontend to ServiceX.',
    long_description=readme,
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'Flask==1.1.2',
        'Flask-WTF==0.14.3',
        'Flask-RESTful==0.3.8',
        'Flask-JWT-Extended==3.24.1',
        'Flask-SQLAlchemy==2.4.3',
        'Flask-Migrate==2.5.3',
        'pika==1.1.0',
        'passlib==1.7.2',
        'confluent-kafka==1.4.2',
        'kubernetes==11.0.0',
        'minio==5.0.10',
        'elasticsearch==7.8.0',
        'psycopg2==2.8.5'
    ],
    extras_require={
        'test': [
            'pytest>=5.2',
            'pytest-flask==1.0.0',
            'coverage>=5.2',
            'codecov==2.1.8',
            'pytest-mock==3.2.0',
            'flake8>=3.8'
        ],
    },
)
