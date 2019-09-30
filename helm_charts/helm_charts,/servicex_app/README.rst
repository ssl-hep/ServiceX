ServiceX REST Server
====================

.. image:: https://travis-ci.org/ssl-hep/ServiceX_transformer.svg?branch=pytest
    :target: https://travis-ci.org/ssl-hep/ServiceX_App
.. image:: https://codecov.io/gh/BenGalewsky/ServiceX_App/branch/pytest/graph/badge.svg
  :target: https://codecov.io/gh/BenGalewsky/ServiceX_App
.. image:: https://img.shields.io/badge/License-BSD%203--Clause-blue.svg
   :target: https://opensource.org/licenses/BSD-3-Clause


Building Docker Image
---------------------

.. code:: bash

   docker build -t servicex_app .

.. image:: doc/sequence_diagram.png

Running Docker
--------------

.. code:: bash

   docker run --name servicex-app --rm -p8000:5000 \
    --mount type=bind,source="$(pwd)"/sqlite,target=/sqlite \
    -e APP_CONFIG_FILE=/home/servicex/docker-dev.conf \
    servicex_app:latest

Cleaning up old Transformation Queues
-------------------------------------

It's easy to accumulate a bunch of transformation queues during testing.
It would be quite tedious to try to delete them via the management
console. You can install the rabbitmqadmin cli and then with some tricky
scripting batch delete queues:

.. code:: bash

   ./d.sh $(python  rabbitmqadmin -V / --port=30182 -u user -p leftfoot1 list queues | grep ".*-.*" | awk '{print $2}')
